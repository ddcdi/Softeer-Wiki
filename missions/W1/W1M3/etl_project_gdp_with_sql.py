import re
import sqlite3
from datetime import datetime
from io import StringIO
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from bs4 import BeautifulSoup


BASE_DIR = Path(__file__).resolve().parent


# ETL 실행 과정을 파일에 기록하는 로그 담당 클래스입니다.
class ETLLogger:
    # 로그 파일 경로를 설정합니다.
    def __init__(self, log_path=BASE_DIR / "etl_project_log.txt"):
        self.log_path = Path(log_path)

    # 현재 시각과 함께 전달받은 메시지를 로그 파일에 추가합니다.
    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%B-%d-%H-%M-%S")

        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{timestamp}, {message}\n")


# 변환된 GDP 데이터를 SQLite 데이터베이스에 저장하는 클래스입니다.
class ExtractSQLiteWriter:
    TABLE_NAME = "Countries_by_GDP"
    REGION_COLUMN = "Region"
    COUNTRY_COLUMN = "Country"
    GDP_COLUMN = "GDP_USD_billion"

    # 데이터베이스 파일 경로와 초기화 여부를 설정합니다.
    def __init__(self, db_path=BASE_DIR / "World_Economies.db"):
        self.db_path = Path(db_path)
        self._initialized = False

    # 기존 테이블을 삭제하고 새 테이블을 만들어 저장 공간을 초기화합니다.
    def reset(self):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(f"DROP TABLE IF EXISTS {self.TABLE_NAME}")
            connection.execute(
                f"""
                CREATE TABLE {self.TABLE_NAME} (
                    {self.REGION_COLUMN} TEXT NOT NULL,
                    {self.COUNTRY_COLUMN} TEXT NOT NULL,
                    {self.GDP_COLUMN} REAL
                )
                """
            )

        self._initialized = True

    # DataFrame에서 필요한 컬럼만 골라 SQLite 테이블에 저장합니다.
    def save(self, df):
        if not self._initialized:
            self.reset()

        db_data = df[[self.REGION_COLUMN, self.COUNTRY_COLUMN, self.GDP_COLUMN]]
        db_data = db_data.where(pd.notna(db_data), None)
        records = db_data.itertuples(index=False, name=None)

        with sqlite3.connect(self.db_path) as connection:
            connection.executemany(
                f"""
                INSERT INTO {self.TABLE_NAME}
                    ({self.REGION_COLUMN}, {self.COUNTRY_COLUMN}, {self.GDP_COLUMN})
                VALUES (?, ?, ?)
                """,
                records,
            )


# 지역별 Wikipedia GDP 표를 수집하는 크롤러 클래스입니다.
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

    # 기본 URL 목록을 사용하거나 외부에서 받은 지역별 URL 목록을 설정합니다.
    def __init__(self, region_urls=None):
        self.region_urls = region_urls or self.REGION_URLS

    # 지정한 지역의 HTML 표를 찾아 DataFrame으로 추출합니다.
    def extract(self, region):
        url = self.region_urls.get(region)
        if url is None:
            raise ValueError(f"Unknown region: {region}")

        html = self._fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        table = self._find_gdp_table(soup)
        return pd.read_html(StringIO(str(table)))[0]

    # User-Agent를 포함해 요청하고 페이지 HTML을 문자열로 반환합니다.
    def _fetch_html(self, url):
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request) as response:
            return response.read().decode("utf-8")

    # 페이지의 wikitable 중 GDP 데이터로 보이는 첫 번째 표를 찾습니다.
    def _find_gdp_table(self, soup):
        for table in soup.select("table.wikitable"):
            text = self._clean_text(table.get_text(" ", strip=True))
            if "GDP" in text or "Country" in text or "Region" in text:
                return table

        raise ValueError("GDP table not found.")

    # 각주 표시와 불필요한 공백을 제거해 비교하기 쉬운 텍스트로 정리합니다.
    @staticmethod
    def _clean_text(value):
        text = "" if pd.isna(value) else str(value)
        text = re.sub(r"\[[^\]]*\]", "", text)
        return " ".join(text.split())


# 수집한 지역별 GDP 표를 표준 컬럼과 단위로 변환하는 클래스입니다.
class RegionalGDPTransformer:
    GDP_COLUMN = ExtractSQLiteWriter.GDP_COLUMN

    EXCLUDED_COUNTRIES = {
        "world",
        "arab world",
        "commonwealth of nations",
        "north america",
        "total",
    }

    # 필터 기준 GDP와 지역별 상위 국가 개수, 현재 연도를 설정합니다.
    def __init__(self, minimum_gdp_billion=100, top_n=5):
        self.minimum_gdp_billion = minimum_gdp_billion
        self.top_n = top_n
        self.current_year = datetime.now().year

    # 원본 표에서 국가와 GDP 컬럼을 찾아 표준 DataFrame으로 변환합니다.
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

    # 국가명에 해당하는 컬럼을 이름 기준으로 찾고, 없으면 첫 컬럼을 사용합니다.
    def _find_country_column(self, df):
        for column in df.columns:
            column_name = str(column).casefold()
            if "country" in column_name or "territory" in column_name or "region" in column_name:
                return column

        return df.columns[0]

    # GDP 후보 컬럼을 단서별로 평가해 실제 GDP 값이 들어 있는 컬럼을 선택합니다.
    def _find_gdp_column(self, df, country_column):
        gdp_candidates = []

        for column in df.columns:
            column_name = str(column).casefold()
            if column == country_column:
                continue

            if "gdp" in column_name and "capita" not in column_name and "ppp" not in column_name:
                gdp_candidates.append(column)

        if gdp_candidates:
            return max(gdp_candidates, key=lambda column: self._column_max_gdp(df[column], column))

        year_columns = self._find_year_columns(df.columns)
        if year_columns:
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

    # 특정 컬럼을 GDP 단위로 변환했을 때의 최대값을 계산해 후보 컬럼 평가에 사용합니다.
    def _column_max_gdp(self, series, column_name):
        values = series.map(lambda value: self._to_billion_usd(value, column_name)).dropna()
        return values.max() if not values.empty else 0

    # 컬럼명 전체가 연도 형태인 컬럼들을 찾아 연도와 원래 컬럼명을 함께 반환합니다.
    def _find_year_columns(self, columns):
        year_columns = []

        for column in columns:
            match = re.fullmatch(r"\D*(\d{4})\D*", str(column))
            if match:
                year_columns.append((int(match.group(1)), column))

        return year_columns

    # 문자열이나 숫자로 들어온 GDP 값을 billion USD 기준의 숫자로 변환합니다.
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

    # MultiIndex, 각주, 중복 이름을 정리해 DataFrame 컬럼명을 다루기 쉽게 만듭니다.
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

    # 지역 합계나 전체 합계처럼 국가별 분석 대상이 아닌 행인지 판단합니다.
    def _is_aggregate(self, region, country):
        country = self._clean_text(country).casefold()
        region = region.casefold()

        return (
            not country
            or country == region
            or country in self.EXCLUDED_COUNTRIES
            or country.startswith("total")
        )

    # 컬럼명이 연도 형태인지 확인해 단위 추정에 활용합니다.
    def _is_year_column(self, column_name):
        return re.fullmatch(r"\D*\d{4}\D*", str(column_name)) is not None

    # 각주 표시와 불필요한 공백을 제거해 표 데이터를 일관된 텍스트로 정리합니다.
    @staticmethod
    def _clean_text(value):
        text = "" if pd.isna(value) else str(value)
        text = re.sub(r"\[[^\]]*\]", "", text)
        return " ".join(text.split())


# SQLite에 저장된 GDP 데이터를 조회하고 출력 형식으로 정리하는 클래스입니다.
class RegionalGDPLoader:
    TABLE_NAME = ExtractSQLiteWriter.TABLE_NAME
    REGION_COLUMN = ExtractSQLiteWriter.REGION_COLUMN
    COUNTRY_COLUMN = ExtractSQLiteWriter.COUNTRY_COLUMN
    GDP_COLUMN = RegionalGDPTransformer.GDP_COLUMN

    # 조회할 데이터베이스 경로와 출력 기준값을 설정합니다.
    def __init__(
        self,
        db_path=BASE_DIR / "World_Economies.db",
        minimum_gdp_billion=100,
        top_n=5,
    ):
        self.db_path = Path(db_path)
        self.minimum_gdp_billion = minimum_gdp_billion
        self.top_n = top_n

    # GDP 기준 조회 결과와 지역별 상위 GDP 평균을 콘솔에 출력합니다.
    def print_result(self):
        countries_over_100b = self.get_countries_over_100b()
        top5_average = self.get_top5_average_by_region()

        print(f"\n{'=' * 20} GDP >= 100B USD {'=' * 20}")
        print(self._to_string(countries_over_100b))

        print(f"\n{'=' * 20} Region Top 5 Average {'=' * 20}")
        print(self._to_string(top5_average))

    # GDP가 기준값 이상인 국가 목록을 높은 GDP 순서로 조회합니다.
    def get_countries_over_100b(self):
        query = f"""
            SELECT
                {self.REGION_COLUMN},
                {self.COUNTRY_COLUMN},
                ROUND({self.GDP_COLUMN}, 2) AS {self.GDP_COLUMN}
            FROM {self.TABLE_NAME}
            WHERE {self.GDP_COLUMN} >= ?
            ORDER BY {self.GDP_COLUMN} DESC, {self.COUNTRY_COLUMN}
        """

        return self._read_sql(query, [self.minimum_gdp_billion])

    # 지역별 GDP 상위 N개 국가의 평균 GDP를 계산해 조회합니다.
    def get_top5_average_by_region(self):
        query = f"""
            SELECT
                {self.REGION_COLUMN},
                ROUND(AVG({self.GDP_COLUMN}), 2) AS "Top {self.top_n} Average GDP_USD_billion"
            FROM (
                SELECT
                    {self.REGION_COLUMN},
                    {self.COUNTRY_COLUMN},
                    {self.GDP_COLUMN},
                    ROW_NUMBER() OVER (
                        PARTITION BY {self.REGION_COLUMN}
                        ORDER BY {self.GDP_COLUMN} DESC
                    ) AS gdp_rank
                FROM {self.TABLE_NAME}
            )
            WHERE gdp_rank <= ?
            GROUP BY {self.REGION_COLUMN}
            ORDER BY {self.REGION_COLUMN}
        """

        return self._read_sql(query, [self.top_n])

    # 전달받은 SQL과 파라미터를 실행하고 결과를 DataFrame으로 반환합니다.
    def _read_sql(self, query, params):
        with sqlite3.connect(self.db_path) as connection:
            return pd.read_sql_query(query, connection, params=params)

    # DataFrame 출력 시 소수점 형식을 고정해 콘솔 결과를 읽기 쉽게 만듭니다.
    def _to_string(self, df):
        float_formatters = {
            column: "{:.2f}".format for column in df.columns if pd.api.types.is_float_dtype(df[column])
        }

        return df.to_string(index=False, formatters=float_formatters)


# 스크립트를 직접 실행할 때 전체 ETL 흐름을 순서대로 수행합니다.
if __name__ == "__main__":
    logger = ETLLogger()
    db_writer = ExtractSQLiteWriter()
    crawler = RegionalGDPTableCrawler()
    transformer = RegionalGDPTransformer()
    loader = RegionalGDPLoader(db_writer.db_path)

    logger.log("ETL process started")
    db_writer.reset()

    for region in crawler.region_urls:
        logger.log(f"Extract started for {region}")
        region_data = crawler.extract(region)
        logger.log(f"Extract ended for {region}")

        logger.log(f"Transform started for {region}")
        transformed_data = transformer.transform(region, region_data)
        logger.log(f"Transform ended for {region}")

        logger.log(f"Load started for {region}")
        db_writer.save(transformed_data)
        logger.log(f"Load ended for {region}")

    logger.log("Output started")
    loader.print_result()
    logger.log("Output ended")
    logger.log("ETL process ended")
