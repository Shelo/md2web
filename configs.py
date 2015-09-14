def parse_configs(filepath):
    configs = open(filepath)

    options = {}
    for line in configs:
        if not line:
            continue

        name, value = line.split("=")
        name = name.strip()
        value = value.strip()

        options[name] = value

    return options
