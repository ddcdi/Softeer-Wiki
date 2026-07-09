from multiprocessing import Process, Queue, current_process
from queue import Empty
import time


def Task(tasks_to_accomplish: Queue, tasks_that_are_done: Queue): # 변수명 겹치지 
    while True:
        try:
            task = tasks_to_accomplish.get_nowait()
        except Empty:
            break
        print(f"{task}")
        time.sleep(0.5)
        tasks_that_are_done.put(f"{task} is done by {current_process().name}")
    return


if __name__ == "__main__":
    tasks_to_accomplish = Queue()
    tasks_that_are_done = Queue()

    for i in range(10):
        task = f"Task no {i}"
        tasks_to_accomplish.put(task)

    processes = []

    for i in range(1, 5):
        p = Process(target=Task, args=(tasks_to_accomplish, tasks_that_are_done))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    for i in range(10):
        try:
            print(tasks_that_are_done.get_nowait())
        except Empty:
            break
