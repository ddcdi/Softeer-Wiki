from multiprocessing import Process


def print_region(region: str = "Asia"):
    print(f"The name of continent is : {region}")


if __name__ == '__main__':
    regions = [None, "America", "Europe", "Africa"]
    processes = []

    for reg in regions:
        if reg is None: # 인자가 없는 경우
            p = Process(target=print_region)
        else:
            p = Process(target=print_region, args=(reg,))
        
        p.start()
        processes.append(p) # 나중에 join하려고 리스트에 보관

    for p in processes:
        p.join()