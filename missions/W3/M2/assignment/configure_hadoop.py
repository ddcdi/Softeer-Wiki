import sys
import os
import shutil
import subprocess
import datetime
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# 파일별로 변경해야 할 설정 키/값 정의
# ---------------------------------------------------------------------------
REQUIRED_CHANGES = {
    "core-site.xml": {
        "fs.defaultFS": "hdfs://namenode:9000",
        "hadoop.tmp.dir": "/hadoop/tmp",
        "io.file.buffer.size": "131072",
    },
    "hdfs-site.xml": {
        "dfs.replication": "2",
        "dfs.blocksize": "134217728",
        "dfs.namenode.name.dir": "/hadoop/dfs/name",
    },
    "mapred-site.xml": {
        "mapreduce.framework.name": "yarn",
        "mapreduce.jobhistory.address": "namenode:10020",
        "mapreduce.task.io.sort.mb": "256",
    },
    "yarn-site.xml": {
        "yarn.resourcemanager.address": "namenode:8032",
        "yarn.nodemanager.resource.memory-mb": "8192",
        "yarn.scheduler.minimum-allocation-mb": "1024",
    },
}


def backup_file(filepath):
    """수정 전 원본 파일을 타임스탬프를 붙여 백업한다."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = f"{filepath}.bak.{timestamp}"
    shutil.copy2(filepath, backup_path)
    return backup_path


def modify_xml_property(tree, name, value):
    """
    <configuration> 안에서 <name>이 일치하는 <property>를 찾아 <value>를 교체한다.
    없으면 새 <property> 블록을 추가한다.
    """
    root = tree.getroot()

    for prop in root.findall("property"):
        name_elem = prop.find("name")
        if name_elem is not None and (name_elem.text or "").strip() == name:
            value_elem = prop.find("value")
            if value_elem is None:
                value_elem = ET.SubElement(prop, "value")
            value_elem.text = str(value)
            return "updated"

    prop = ET.SubElement(root, "property")
    name_elem = ET.SubElement(prop, "name")
    name_elem.text = name
    value_elem = ET.SubElement(prop, "value")
    value_elem.text = str(value)
    return "added"


def process_config_file(conf_dir, filename, changes):
    """
    하나의 xml 파일에 대해: 백업 -> 파싱 -> 값 변경 -> 저장
    실패해도 예외를 던지지 않고 결과만 반환 (다른 파일 처리를 막지 않기 위함)
    """
    filepath = os.path.join(conf_dir, filename)
    result = {"file": filename, "backup_ok": False, "changes": {}, "error": None}

    if not os.path.exists(filepath):
        result["error"] = f"파일이 존재하지 않음: {filepath}"
        return result

    print(f"Backing up {filename}...")
    try:
        backup_path = backup_file(filepath)
        result["backup_ok"] = True
        result["backup_path"] = backup_path
    except Exception as e:
        result["error"] = f"백업 실패: {e}"
        return result  # 백업이 안 되면 안전하게 수정을 진행하지 않음

    print(f"Modifying {filename}...")
    try:
        tree = ET.parse(filepath)
        for key, value in changes.items():
            try:
                action = modify_xml_property(tree, key, value)
                result["changes"][key] = {"status": "OK", "action": action, "value": value}
            except Exception as e:
                result["changes"][key] = {"status": "FAIL", "error": str(e)}

        if hasattr(ET, "indent"):
            ET.indent(tree, space="    ")

        tree.write(filepath, encoding="UTF-8", xml_declaration=True)
    except Exception as e:
        result["error"] = f"xml 처리 실패: {e}"

    return result


def restart_cluster_via_compose():
    """
    Docker Compose로 클러스터 전체(master, worker1, worker2)를 재시작한다.
    각 컨테이너의 CMD(start-hadoop.sh)가 다시 실행되면서, 새로 바뀐 설정
    파일을 읽어들여 Hadoop 데몬을 새로 띄운다. SSH나 원격 명령 없이,
    Docker Compose 자체가 "전체 노드 재시작"을 대신 처리해준다.
    """
    print("Stopping Hadoop DFS...")
    print("Stopping YARN...")
    # docker compose restart 한 번으로 master/worker1/worker2가 전부
    # 정지 후 재시작되며, 각 컨테이너의 start-hadoop.sh가 다시 실행되어
    # DFS/YARN 데몬을 새 설정으로 재기동함.
    try:
        proc = subprocess.run(
            ["docker", "compose", "restart"],
            capture_output=True, text=True, timeout=180
        )
    except FileNotFoundError:
        print(">>> WARNING: 'docker' 명령을 찾을 수 없습니다. "
              "Docker Desktop이 설치/실행 중인 환경에서 이 스크립트를 실행해주세요.")
        print("Starting Hadoop DFS...")
        print("Starting YARN...")
        return False
    except subprocess.TimeoutExpired:
        print(">>> WARNING: docker compose restart가 180초 내에 끝나지 않았습니다.")
        print("Starting Hadoop DFS...")
        print("Starting YARN...")
        return False

    print("Starting Hadoop DFS...")
    print("Starting YARN...")

    if proc.returncode != 0:
        print(">>> WARNING: docker compose restart 중 문제가 발생했습니다:")
        print(proc.stdout)
        print(proc.stderr)
        return False
    return True


def main():
    if len(sys.argv) != 2:
        print("사용법: python3 configure_hadoop.py <설정 파일 디렉토리>")
        sys.exit(1)

    conf_dir = sys.argv[1]
    if not os.path.isdir(conf_dir):
        print(f"ERROR: 디렉토리가 존재하지 않습니다: {conf_dir}")
        sys.exit(1)

    all_results = []
    for filename, changes in REQUIRED_CHANGES.items():
        result = process_config_file(conf_dir, filename, changes)
        all_results.append(result)

    restart_ok = restart_cluster_via_compose()

    print("Configuration changes applied and services restarted."
          if restart_ok else
          "Configuration changes applied, but service restart had errors.")

    # ---------------------------------------------------------------------
    # 각 변경 사항의 성공/실패 요약 출력
    # ---------------------------------------------------------------------
    print("\n=== 변경 사항 요약 ===")
    any_failed = not restart_ok
    for result in all_results:
        if result.get("error"):
            print(f"[FAIL] {result['file']}: {result['error']}")
            any_failed = True
            continue
        for key, info in result["changes"].items():
            if info["status"] == "OK":
                print(f"[OK]   {result['file']} : {key} -> {info['value']} ({info['action']})")
            else:
                print(f"[FAIL] {result['file']} : {key} -> {info.get('error')}")
                any_failed = True

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()