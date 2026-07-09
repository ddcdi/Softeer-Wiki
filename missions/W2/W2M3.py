from multiprocessing import Process, Queue
from dataclasses import dataclass
from typing import List

@dataclass
class Item:
    num: int
    color: str

def Push(items: List[Item], q: Queue):
    print("pushing items to queue:")
    for item in items:
        q.put(item)
        print(f"item no: {item.num} {item.color}")

def Pop(q: Queue):
    print("popping items from queue:")
    while not q.empty():
        item = q.get()
        print(f"item no: {item.num} {item.color}")

if __name__ == "__main__":
    items = [Item(1, "red"), Item(2, "green"), Item(3, "blue"), Item(4, "black")]
    q = Queue()

    p1 = Process(target=Push, args=(items, q))
    p2 = Process(target=Pop, args=(q,))

    p1.start()
    p1.join()

    p2.start()
    p2.join()
