def log_node(name, fn):
    def wrapper(state):
        print(f"\n🚀 ENTER NODE: {name}")
        return fn(state)
    return wrapper