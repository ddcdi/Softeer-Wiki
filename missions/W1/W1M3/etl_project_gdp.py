import json
import re
from datetime import datetime
from io import StringIO
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parent


# ETL 실행 과정을 파일에 기록하는 로거 클래스입니다.
class ETLLogger:
    # 로그 파일 경로를 설정합니다.
    def __init__(self, log_path=BASE_DIR / "etl_project_log.txt"):
        self.log_path = Path(log_path)

    # 현재 시각과 함께 전달받은 메시지를 로그 파일에 한 줄씩 저장합니다.
    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%B-%d-%H-%M-%S")

        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{timestamp}, {message}\n")


# 추출 단계에서 얻은 원본 GDP 표를 지역별 JSON 파일로 저장하는 클래스입니다.
class ExtractJSONWriter:
    # JSON 출력 경로와 저장할 데이터 컨테이너를 초기화합니다.
    def __init__(self, output_path=BASE_DIR / "Countries_by_GDP.json"):
        self.output_path = Path(output_path)
        self.data = {}

    # 지역명을 키로 사용해 데이터프레임을 JSON 직렬화 가능한 형태로 저장합니다.
    def save(self, region, df):
        self.data[region] = self._to_records(df)

        with self.output_path.open("w", encoding="utf-8") as json_file:
            json.dump(self.data, json_file, ensure_ascii=False, indent=2, default=str)

    # 데이터프레임의 컬럼명과 결측치를 정리한 뒤 레코드 목록으로 변환합니다.
    def _to_records(self, df):
        df = df.copy()
        df.columns = self._clean_columns(df.columns)
        df = df.where(pd.notna(df), None)
        return df.to_dict(orient="records")

    # 중복되거나 여러 단계로 구성된 컬럼명을 JSON에서 쓰기 쉬운 문자열로 정리합니다.
    def _clean_columns(self, columns):
        clean_columns = []
        used_columns = {}

        for column in columns:
            if isinstance(column, tuple):
                parts = [
                    str(part)
                    for part in column
                    if "Unnamed" not in str(part) and str(part).casefold() != "nan"
                ]
                column = " ".join(dict.fromkeys(parts))

            column = self._clean_text(column)
            used_columns[column] = used_columns.get(column, 0) + 1

            if used_columns[column] > 1:
                column = f"{column}_{used_columns[column]}"

            clean_columns.append(column)

        return clean_columns

    # 각주 표기와 불필요한 공백을 제거해 텍스트를 표준화합니다.
    @staticmethod
    def _clean_text(value):
        text = "" if pd.isna(value) else str(value)
        text = re.sub(r"\[[^\]]*\]", "", text)
        return " ".join(text.split())


# 위키피디아의 지역별 GDP 문서에서 GDP 표를 추출하는 크롤러 클래스입니다.
class RegionalGDPTableCrawler:
    REGION_URLS = {
        "Africa": "https://en.wikipedia.org/wiki/List_of_African_countries_by_GDP_%28nominal%29",
        "Arab League": "https://en.wikipedia.org/wiki/List_of_Arab_League_countries_by_GDP_%28nominal%29",
        "Asia-Pacific": "https://en.wikipedia.org/wiki/List_of_countries_in_Asia-Pacific_by_GDP_%28nominal%29",
        "Commonwealth": "https://en.wikipedia.org/wiki/List_of_Commonwealth_of_Nations_countries_by_GDP_%28nominal%29",
        "Latin America and Caribbean": "https://en.wikipedia.org/wiki/List_of_Latin_American_and_Caribbean_countries_by_GDP_%28nominal%29",
        "North America": "https://en.wikipedia.org/wiki/List_of_North_American_countries_by_GDP_%28nominal%29",
        "Oceania": "https://en.wikipedia.org/wiki/List_of_Oceanian_countries_by_GDP",
        "Europe": "https://en.wikipedia.org/wiki/List_of_sovereign_states_in_Europe_by_GDP_%28nominal%29",
    }

    # 크롤링할 지역별 URL 목록을 설정합니다.
    def __init__(self, region_urls=None):
        self.region_urls = region_urls or self.REGION_URLS

    # 지정한 지역의 HTML을 가져와 첫 번째 GDP 관련 표를 데이터프레임으로 변환합니다.
    def extract(self, region):
        url = self.region_urls.get(region)
        if url is None:
            raise ValueError(f"Unknown region: {region}")

        html = self._fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        table = self._find_gdp_table(soup)
        return pd.read_html(StringIO(str(table)))[0]

    # User-Agent를 포함한 요청으로 웹 페이지 HTML을 다운로드합니다.
    def _fetch_html(self, url):
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request) as response:
            return response.read().decode("utf-8")

    # 문서 안의 wikitable 중 GDP, 국가, 지역 정보가 들어 있는 표를 찾습니다.
    def _find_gdp_table(self, soup):
        for table in soup.select("table.wikitable"):
            text = self._clean_text(table.get_text(" ", strip=True))
            if "GDP" in text or "Country" in text or "Region" in text:
                return table

        raise ValueError("GDP table not found.")

    # 표 안의 각주 표기와 중복 공백을 제거해 검색하기 쉬운 텍스트로 만듭니다.
    @staticmethod
    def _clean_text(value):
        text = "" if pd.isna(value) else str(value)
        text = re.sub(r"\[[^\]]*\]", "", text)
        return " ".join(text.split())


# 원본 GDP 표를 분석하기 좋은 표준 컬럼 구조로 변환하는 클래스입니다.
class RegionalGDPTransformer:
    GDP_COLUMN = "GDP (1B USD)"

    EXCLUDED_COUNTRIES = {
        "world",
        "arab world",
        "commonwealth of nations",
        "north america",
        "total",
    }

    # GDP 필터 기준, 상위 국가 개수, 현재 연도를 설정합니다.
    def __init__(self, minimum_gdp_billion=100, top_n=5):
        self.minimum_gdp_billion = minimum_gdp_billion
        self.top_n = top_n
        self.current_year = datetime.now().year

    # 지역별 원본 표에서 국가명과 GDP 값을 추출하고 10억 달러 단위로 정규화합니다.
    def transform(self, region, df):
        df = df.copy()
        df.columns = self._clean_columns(df.columns)
        df = df.dropna(how="all")

        country_column = self._find_country_column(df)
        gdp_column = self._find_gdp_column(df, country_column)

        transformed = pd.DataFrame(
            {
                "Region": region,
                "Country": df[country_column].map(self._clean_text),
                self.GDP_COLUMN: df[gdp_column].map(
                    lambda value: self._to_billion_usd(value, gdp_column)
                ),
            }
        )

        transformed = transformed.dropna(subset=[self.GDP_COLUMN])
        transformed = transformed[
            ~transformed["Country"].map(lambda country: self._is_aggregate(region, country))
        ]
        transformed[self.GDP_COLUMN] = transformed[self.GDP_COLUMN].round(2)

        return transformed.sort_values(self.GDP_COLUMN, ascending=False).reset_index(drop=True)

    # 국가명, 영토명, 지역명을 담고 있는 컬럼을 찾아 반환합니다.
    def _find_country_column(self, df):
        for column in df.columns:
            column_name = str(column).casefold()
            if "country" in column_name or "territory" in column_name or "region" in column_name:
                return column

        return df.columns[0]

    # GDP 후보 컬럼 중 실제 GDP 금액으로 가장 적절한 컬럼을 선택합니다.
    def _find_gdp_column(self, df, country_column):
        gdp_candidates = []

        for column in df.columns:
            column_name = str(column).casefold()
            if column == country_column:
                continue
            
            # GDP 총액을 10억 달러 단위로 분석하려는 거라서 1인당 GDP나 PPP 기준 GDP를 쓰면 결과가 틀어지기 때문에 제외합니다.
            if "gdp" in column_name and "capita" not in column_name and "ppp" not in column_name:
                gdp_candidates.append(column)

        # GDP 후보 컬럼이 존재하면 최대값을 기준으로 가장 적절한 컬럼을 반환합니다.
        if gdp_candidates:
            return max(gdp_candidates, key=lambda column: self._column_max_gdp(df[column], column))

        # GDP 후보 컬럼이 없으면 연도 컬럼을 찾아 가장 최근 연도의 GDP 컬럼을 반환합니다.
        year_columns = self._find_year_columns(df.columns)
        if year_columns:
            # 연도 컬럼 중 현재 연도 이하의 컬럼만 필터링하고, 존재하면 가장 최근 연도의 컬럼을 반환합니다.
            past_year_columns = [
                (year, column) for year, column in year_columns if year <= self.current_year
            ]
            if past_year_columns:
                return max(past_year_columns)[1]

            return min(year_columns)[1]

        numeric_columns = [
            column
            for column in df.columns
            if column != country_column and self._column_max_gdp(df[column], column) > 0
        ]
        if numeric_columns:
            return max(numeric_columns, key=lambda column: self._column_max_gdp(df[column], column))

        raise ValueError("GDP column not found.")

    # 특정 컬럼의 값을 10억 달러 단위로 변환했을 때의 최대값을 계산합니다.
    def _column_max_gdp(self, series, column_name):
        values = series.map(lambda value: self._to_billion_usd(value, column_name)).dropna()
        return values.max() if not values.empty else 0

    # 컬럼명에서 4자리 연도를 찾아 연도 컬럼 후보 목록을 만듭니다.
    def _find_year_columns(self, columns):
        year_columns = []

        for column in columns:
            match = re.fullmatch(r"\D*(\d{4})\D*", str(column))
            if match:
                year_columns.append((int(match.group(1)), column))

        return year_columns

    # 문자열 또는 숫자 형태의 GDP 값을 10억 달러 단위의 숫자로 변환합니다.
    def _to_billion_usd(self, value, column_name):
        text = self._clean_text(value)
        if not text or text in {"-", "--", "—"}:
            return None

        number_match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?", text)
        if number_match is None:
            return None

        number = float(number_match.group().replace(",", ""))
        text_lower = text.casefold()
        column_lower = str(column_name).casefold()

        if "trillion" in text_lower or "trillion" in column_lower:
            return number * 1000

        if "billion" in text_lower or "billion" in column_lower:
            return number

        if (
            "million" in text_lower
            or "million" in column_lower
            or "$mil" in column_lower
            or self._is_year_column(column_name)
            or number >= 10000
        ):
            return number / 1000

        return number

    # 원본 표의 복합 컬럼명, 각주, 중복 이름을 분석용 컬럼명으로 정리합니다.
    def _clean_columns(self, columns):
        clean_columns = []
        used_columns = {}

        for column in columns:
            if isinstance(column, tuple):
                parts = [
                    str(part)
                    for part in column
                    if "Unnamed" not in str(part) and str(part).casefold() != "nan"
                ]
                column = " ".join(dict.fromkeys(parts))

            column = self._clean_text(column)
            used_columns[column] = used_columns.get(column, 0) + 1

            if used_columns[column] > 1:
                column = f"{column}_{used_columns[column]}"

            clean_columns.append(column)

        return clean_columns

    # 지역 합계나 전체 세계처럼 개별 국가가 아닌 집계 행인지 판단합니다.
    def _is_aggregate(self, region, country):
        country = self._clean_text(country).casefold()
        region = region.casefold()

        return (
            not country
            or country == region
            or country in self.EXCLUDED_COUNTRIES
            or country.startswith("total")
        )

    # 컬럼명이 연도만 나타내는 형태인지 확인합니다.
    def _is_year_column(self, column_name):
        return re.fullmatch(r"\D*\d{4}\D*", str(column_name)) is not None

    # 각주 표기와 중복 공백을 제거해 비교 가능한 텍스트로 정리합니다.
    @staticmethod
    def _clean_text(value):
        text = "" if pd.isna(value) else str(value)
        text = re.sub(r"\[[^\]]*\]", "", text)
        return " ".join(text.split())


# 변환된 지역별 GDP 데이터를 모아 최종 분석 결과를 출력하는 클래스입니다.
class RegionalGDPLoader:
    GDP_COLUMN = RegionalGDPTransformer.GDP_COLUMN

    # 출력 기준값과 지역별 상위 국가 수, 누적 테이블 저장소를 초기화합니다.
    def __init__(self, minimum_gdp_billion=100, top_n=5):
        self.minimum_gdp_billion = minimum_gdp_billion
        self.top_n = top_n
        self.tables = []

    # 변환된 지역별 GDP 데이터프레임을 내부 목록에 저장합니다.
    def load(self, transformed_data):
        self.tables.append(transformed_data.copy())

    # GDP 기준 필터 결과와 지역별 상위 평균 GDP 결과를 콘솔에 출력합니다.
    def print_result(self):
        countries_over_100b = self.get_countries_over_100b()
        top5_average = self.get_top5_average_by_region()

        print(f"\n{'=' * 20} GDP >= 100B USD {'=' * 20}")
        print(self._to_string(countries_over_100b))

        print(f"\n{'=' * 20} Region Top 5 Average {'=' * 20}")
        print(self._to_string(top5_average))

    # 전체 데이터에서 GDP가 기준값 이상인 국가만 추려 내림차순으로 반환합니다.
    def get_countries_over_100b(self):
        df = self._merged_table()

        return (
            df[df[self.GDP_COLUMN] >= self.minimum_gdp_billion]
            .sort_values(self.GDP_COLUMN, ascending=False)
            .reset_index(drop=True)
        )

    # 지역별 GDP 상위 N개 국가의 평균 GDP를 계산합니다.
    def get_top5_average_by_region(self):
        df = self._merged_table()
        top5 = (
            df.sort_values(["Region", self.GDP_COLUMN], ascending=[True, False])
            .groupby("Region")
            .head(self.top_n)
        )

        return (
            top5.groupby("Region", as_index=False)[self.GDP_COLUMN]
            .mean()
            .rename(columns={self.GDP_COLUMN: f"Top {self.top_n} Average GDP (1B USD)"})
            .round(2)
        )

    # 지금까지 적재된 지역별 데이터프레임들을 하나의 데이터프레임으로 합칩니다.
    def _merged_table(self):
        if not self.tables:
            return pd.DataFrame(columns=["Region", "Country", self.GDP_COLUMN])

        return pd.concat(self.tables, ignore_index=True)

    # 데이터프레임을 소수점 두 자리 형식의 문자열 표로 변환합니다.
    def _to_string(self, df):
        float_formatters = {
            column: "{:.2f}".format for column in df.columns if pd.api.types.is_float_dtype(df[column])
        }

        return df.to_string(index=False, formatters=float_formatters)


if __name__ == "__main__":
    logger = ETLLogger()
    json_writer = ExtractJSONWriter()
    crawler = RegionalGDPTableCrawler()
    transformer = RegionalGDPTransformer()
    loader = RegionalGDPLoader()

    logger.log("ETL process started")

    for region in crawler.region_urls:
        logger.log(f"Extract started for {region}")
        region_data = crawler.extract(region)
        json_writer.save(region, region_data)
        logger.log(f"Extract ended for {region}")

        logger.log(f"Transform started for {region}")
        transformed_data = transformer.transform(region, region_data)
        logger.log(f"Transform ended for {region}")

        logger.log(f"Load started for {region}")
        loader.load(transformed_data)
        logger.log(f"Load ended for {region}")

    logger.log("Output started")
    loader.print_result()
    logger.log("Output ended")
    logger.log("ETL process ended")
