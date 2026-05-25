def run(args):
    # Обработка разных форматов args
    if isinstance(args, str):
        try:
            args = eval(args)
        except:
            args = {"a": 0, "b": 0}

    a = args.get("a", 0)
    b = args.get("b", 0)
    result = a + b
    return {"result": result, "a": a, "b": b}

