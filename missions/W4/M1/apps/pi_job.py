import sys

# pyspark.sql.functions는 Spark DataFrame에서 사용할 수 있는 함수 모음입니다.
# 예: rand(), sum(), count(), when(), col(), lit() 같은 함수를 F.rand(...) 형태로 사용합니다.
from pyspark.sql import functions as F
# SparkSession은 Spark 애플리케이션의 시작점입니다.
# DataFrame을 읽고, 변환하고, 저장하려면 SparkSession이 필요합니다.
from pyspark.sql import SparkSession


# 입력 경로의 파일 확장자에 따라 적절한 Spark reader로 데이터셋을 읽는 함수
def read_dataset(spark: SparkSession, input_path: str):
    lower_path = input_path.lower()

    # 입력 경로가 .parquet으로 끝나면 Parquet 형식으로 읽습니다.
    # Parquet은 Spark에서 자주 쓰는 컬럼 기반 저장 형식입니다.
    if lower_path.endswith(".parquet"):
        return spark.read.parquet(input_path)

    if lower_path.endswith(".json") or lower_path.endswith(".jsonl"):
        return spark.read.json(input_path)

    if lower_path.endswith(".csv"):
        # header=true: 첫 번째 줄을 컬럼명으로 사용
        # inferSchema=true: 문자열뿐 아니라 숫자 타입 등을 Spark가 자동으로 추론합니다.
        return spark.read.option("header", "true").option("inferSchema", "true").csv(input_path)

    # 위 확장자에 해당하지 않으면 기본적으로 일반 텍스트 파일로 읽습니다.
    # 이 경우 DataFrame에는 value라는 문자열 컬럼 하나가 생깁니다.
    return spark.read.text(input_path)

if __name__ == "__main__":
    """
        Usage: pi_job.py <input_path> <output_path> [partitions]
    """
    # SparkSession.builder는 Spark 애플리케이션 설정을 시작
    spark = (
        # Spark UI와 로그에 표시될 애플리케이션 이름을 지정
        SparkSession.builder
        .appName("PythonPi")
        # 기존 SparkSession이 있으면 재사용하고, 없으면 새로 생성
        .getOrCreate()
    )

    # 실행 인자가 부족하면 올바른 사용법을 보여주고 프로그램을 종료
    if len(sys.argv) < 3:
        # SparkSession을 만든 뒤 종료하는 상황이므로 리소스를 정리
        spark.stop()
        # SystemExit을 발생시켜 프로그램을 종료하면서 사용법 메시지를 출력합니다.
        raise SystemExit("Usage: pi_job.py <input_path> <output_path> [partitions]")

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    # 세 번째 실행 인자가 있으면 partition 개수로 사용하고, 없으면 기본값 2를 사용
    # partition은 Spark가 데이터를 나누어 병렬 처리하는 단위
    partitions = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    # 입력 경로에서 데이터셋을 읽고, 지정한 partition 개수로 다시 나눈다.
    # 이 스크립트에서는 데이터셋의 각 row를 몬테카를로 샘플 1개처럼 사용합니다.
    dataset = read_dataset(spark, input_path).repartition(partitions)

    sample_count = dataset.count()

    if sample_count == 0:
        spark.stop()
        raise SystemExit("Input dataset is empty. Monte Carlo estimation requires at least one row.")

    # 몬테카를로 방법으로 π를 추정하기 위한 샘플 DataFrame을 만든다.
    samples = (
        # 입력 데이터셋의 row 개수만큼 랜덤 좌표를 만들기 위해 dataset에서 시작.
        dataset
        # select는 필요한 컬럼만 골라 새 DataFrame을 만드는 변환입니다.
        .select(
            # F.rand(seed=42)는 0 이상 1 미만의 랜덤 값을 생성합니다.
            # 여기에 * 2 - 1을 적용해 -1 이상 1 미만의 x좌표로 바꿉니다.
            # seed를 고정하면 같은 입력에 대해 재현 가능한 난수를 만들 수 있습니다.
            (F.rand(seed=42) * 2 - 1).alias("x"),
            # y좌표도 x와 같은 방식으로 만들되, 다른 seed를 사용해 독립적인 난수열로 만듭니다.
            (F.rand(seed=43) * 2 - 1).alias("y"),
        )
        # withColumn은 기존 DataFrame에 새 컬럼을 추가하거나 기존 컬럼을 바꾸는 변환
        # 여기서는 점 (x, y)가 반지름 1인 원 안에 있는지 나타내는 컬럼을 추가
        .withColumn("is_inside_circle", F.when(F.col("x") ** 2 + F.col("y") ** 2 <= 1, 1).otherwise(0))
    )

    # 샘플 DataFrame을 집계해서 최종 결과 DataFrame을 만든다.
    result = (
        samples
        # is_inside_circle 값이 1인 row를 모두 더하면 원 안에 들어간 점의 개수가 된다.
        .agg(F.sum("is_inside_circle").alias("inside_count"), F.count("*").alias("sample_count"))
        # π 추정 공식:
        # 정사각형 넓이 = 2 * 2 = 4
        # 단위원 넓이 = π
        # 원 안에 들어간 점 비율 ≈ π / 4
        # 따라서 π ≈ 4 * 원 안 점 개수 / 전체 점 개수
        .withColumn("pi_estimate", F.col("inside_count") * 4.0 / F.col("sample_count"))
        # 결과를 나중에 봤을 때 어떤 입력 데이터로 만든 결과인지 알 수 있도록 입력 경로를 컬럼으로 추가한다.
        .withColumn("input_path", F.lit(input_path))

        .select("input_path", "sample_count", "inside_count", "pi_estimate")
    )

    # coalesce(1)은 결과 파일을 partition 1개로 줄여 part 파일이 하나만 나오게 합니다.
    # write.mode("overwrite")는 output_path가 이미 있으면 덮어씁니다.
    # option("header", "true")는 CSV 첫 줄에 컬럼명을 함께 저장합니다.
    # csv(output_path)는 결과 DataFrame을 CSV 파일 형식으로 지정된 경로에 저장합니다.
    result.coalesce(1).write.mode("overwrite").option("header", "true").csv(output_path)

    # Spark 작업 결과를 터미널에서도 바로 확인할 수 있게 출력합니다.
    # truncate=False는 긴 문자열 컬럼을 잘라내지 않고 보여주겠다는 뜻입니다.
    result.show(truncate=False)

    # Spark 애플리케이션이 끝났으므로 SparkSession을 종료하고 리소스를 반납합니다.
    spark.stop()
