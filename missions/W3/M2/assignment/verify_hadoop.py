import subprocess
import sys
import argparse
import json
import urllib.request
import tempfile
import os
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# 1. 검증할 설정값 목록
#
#    [원인 분석] 'getconf -confKey' 서브커맨드는 hdfs 명령어에만 존재하고,
#    hadoop/yarn 명령어에는 애초에 구현되어 있지 않다 (실행하면 usage 도움말이
#    출력됨). 게다가 hdfs getconf가 내부적으로 쓰는 Configuration 객체는
#    core-site.xml, hdfs-site.xml만 로드하도록 되어 있지만 mapred-site.xml/
#    yarn-site.xml 값은 같은 Configuration 객체를 쓰기 때문에 읽어올 수 있다.
#    그래서 core/hdfs 설정은 'hdfs getconf'로, mapred/yarn 설정은 xml 파일을
#    직접 읽어서 확인한다.
# ---------------------------------------------------------------------------
GETCONF_CHECKS = [
    ("fs.defaultFS",          "hdfs://namenode:9000"),
    ("hadoop.tmp.dir",         "/hadoop/tmp"),
    ("io.file.buffer.size",    "131072"),
    ("dfs.replication",        "2"),
    ("dfs.blocksize",           "134217728"),
    ("dfs.namenode.name.dir",   "/hadoop/dfs/name"),
]

XML_FILE_CHECKS = [
    ("mapred-site.xml", "mapreduce.framework.name",       "yarn"),
    ("mapred-site.xml", "mapreduce.jobhistory.address",    "namenode:10020"),
    ("mapred-site.xml", "mapreduce.task.io.sort.mb",        "256"),
    ("yarn-site.xml",   "yarn.resourcemanager.address",      "namenode:8032"),
    ("yarn-site.xml",   "yarn.nodemanager.resource.memory-mb", "8192"),
    ("yarn-site.xml",   "yarn.scheduler.minimum-allocation-mb", "1024"),
]

PASS_COUNT = 0
FAIL_COUNT = 0


def record(is_pass):
    global PASS_COUNT, FAIL_COUNT
    if is_pass:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1


def read_xml_property(filepath, name):
    """xml 파일에서 특정 property의 value 텍스트를 읽어온다."""
    try:
        tree = ET.parse(filepath)
        for prop in tree.getroot().findall("property"):
            name_elem = prop.find("name")
            if name_elem is not None and (name_elem.text or "").strip() == name:
                value_elem = prop.find("value")
                return (value_elem.text or "").strip() if value_elem is not None else None
    except Exception:
        return None
    return None


def check_config_values():
    """1) 설정값이 기대값과 일치하는지 확인 (core/hdfs는 getconf, mapred/yarn은 xml 직접 읽기)"""
    print("\n[1] 설정값 검증 (core/hdfs)")
    for key, expected in GETCONF_CHECKS:
        cmd = ["hdfs", "getconf", "-confKey", key]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            actual = proc.stdout.strip()
        except Exception as e:
            actual = f"ERROR: {e}"

        if actual == expected:
            print(f"PASS: {cmd} -> {actual}")
            record(True)
        else:
            print(f"FAIL: {cmd} -> {actual} (expected {expected})")
            record(False)

    print("\n[1-2] 설정값 검증 (mapred/yarn, xml 직접 확인)")
    conf_dir = os.environ.get("HADOOP_CONF_DIR", "/opt/hadoop/etc/hadoop")
    for filename, key, expected in XML_FILE_CHECKS:
        filepath = os.path.join(conf_dir, filename)
        actual = read_xml_property(filepath, key)
        label = f"[{filename}] {key}"

        if actual == expected:
            print(f"PASS: {label} -> {actual}")
            record(True)
        else:
            print(f"FAIL: {label} -> {actual} (expected {expected})")
            record(False)


def check_default_fs():
    """2) 기본 파일시스템(fs.defaultFS)이 실제로 그 주소로 동작하는지 hdfs dfs -ls로 확인"""
    print("\n[2] 기본 파일시스템 동작 확인")
    cmd = ["hdfs", "dfs", "-ls", "/"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        ok = proc.returncode == 0
    except Exception:
        ok = False

    if ok:
        print(f"PASS: {cmd} -> 정상 응답 (기본 파일시스템 접근 가능)")
    else:
        print(f"FAIL: {cmd} -> 접근 실패")
    record(ok)


def check_replication_factor(expected=2):
    """3) 테스트 파일을 만들고 실제 Replication Factor를 확인"""
    print("\n[3] HDFS 복제 계수(Replication Factor) 확인")

    test_hdfs_path = "/verify_test/replication_test.txt"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hadoop replication verification test\n")
        local_path = f.name

    try:
        subprocess.run(["hdfs", "dfs", "-mkdir", "-p", "/verify_test"],
                        capture_output=True, text=True, timeout=30)
        subprocess.run(["hdfs", "dfs", "-put", "-f", local_path, test_hdfs_path],
                        capture_output=True, text=True, timeout=30)

        proc = subprocess.run(["hdfs", "dfs", "-stat", "%r", test_hdfs_path],
                               capture_output=True, text=True, timeout=30)
        actual = proc.stdout.strip()

        if actual == str(expected):
            print(f"PASS: Replication factor is {actual}")
            record(True)
        else:
            print(f"FAIL: Replication factor is {actual} (expected {expected})")
            record(False)
    finally:
        os.remove(local_path)


def check_mapreduce_job():
    """4) 간단한 MapReduce Job(Pi 예제)을 실행해서 YARN 위에서 정상 동작하는지 확인"""
    print("\n[4] MapReduce Job 실행 확인 (YARN 프레임워크 사용 여부)")

    hadoop_home = os.environ.get("HADOOP_HOME", "/opt/hadoop")
    jar_path = os.path.join(
        hadoop_home, "share", "hadoop", "mapreduce", "hadoop-mapreduce-examples-3.3.6.jar"
    )
    cmd = ["hadoop", "jar", jar_path, "pi", "2", "10"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        output = proc.stdout + proc.stderr
        success = proc.returncode == 0 and "Job" in output and "completed successfully" in output
    except Exception as e:
        success = False
        output = str(e)

    if success:
        print(f"PASS: MapReduce Job(pi) 정상 실행됨 (YARN 프레임워크 사용)")
        record(True)
    else:
        print(f"FAIL: MapReduce Job 실행 실패")
        print(output[-500:])  # 실패시 마지막 500자만 출력
        record(False)


def check_yarn_memory(rm_host):
    """5) ResourceManager REST API로 클러스터 전체 사용 가능 메모리 조회"""
    print("\n[5] YARN 클러스터 메모리 확인")

    url = f"http://{rm_host}:8088/ws/v1/cluster/metrics"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        total_mb = data.get("clusterMetrics", {}).get("totalMB")
        print(f"INFO: {url} -> totalMB = {total_mb}")
        if total_mb is not None and total_mb > 0:
            print(f"PASS: YARN 클러스터 전체 메모리 조회 성공 (totalMB={total_mb})")
            record(True)
        else:
            print(f"FAIL: totalMB 값을 확인할 수 없음")
            record(False)
    except Exception as e:
        print(f"FAIL: ResourceManager REST API 호출 실패 ({e})")
        record(False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rm-host", default="namenode",
                         help="ResourceManager 호스트명 (기본값: namenode)")
    args = parser.parse_args()

    check_config_values()
    check_default_fs()
    check_replication_factor(expected=2)
    check_mapreduce_job()
    check_yarn_memory(args.rm_host)

    print(f"\n=== 검증 결과: PASS {PASS_COUNT} / FAIL {FAIL_COUNT} ===")
    sys.exit(1 if FAIL_COUNT > 0 else 0)


if __name__ == "__main__":
    main()