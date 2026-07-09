from multiprocessing import Pool
from dataclasses import dataclass
import time

@dataclass
class Work:
    name: str
    time: int

def work_log(work: Work):
    print(f"Process {work.name} waiting {work.time} seconds")
    time.sleep(work.time)
    print(f"Process {work.name} Finished.")
    return

if __name__ == "__main__":
    with Pool(processes=2) as pool:
        inputs = [Work("A", 5), Work("B", 2), Work("C", 1), Work("D", 3)]
        results = pool.map(work_log, inputs)

