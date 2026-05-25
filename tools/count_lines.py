def run(args):
    text = args.get('text', '')
    if not text:
        return {'lines': 0}
    lines = len(text.split('\n'))
    return {'lines': lines}