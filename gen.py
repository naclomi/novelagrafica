#!/usr/bin/env python3
import jinja2
import yaml
import sys
import copy
import os
import shutil
import time
import datetime

def generate(book):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('templates/'),
        autoescape=jinja2.select_autoescape()
    )

    shutil.copytree("skeleton", "output", dirs_exist_ok=True)

    pattern_env = jinja2.Environment(
        loader=jinja2.DictLoader(book["patterns"])
    )

    page_vars = []
    for idx in range(len(book["pages"])):
        page_vars.append(copy.deepcopy(book["base"]))
        page_vars[-1].update(book["pages"][idx])
        for template_name in pattern_env.list_templates():
            if template_name not in book["pages"][idx]:
                page_vars[-1][template_name] = pattern_env.get_template(template_name).render(**page_vars[idx])

    for idx in range(len(book["pages"])):
        page_vars[idx]["first"] = page_vars[0]
        page_vars[idx]["last"] = page_vars[-1]
        if idx > 0:
            page_vars[idx]["prev"] = page_vars[idx-1]
        else:
            page_vars[idx]["prev"] = None
        if idx < len(book["pages"])-1:
            page_vars[idx]["next"] = page_vars[idx+1]
        else:
            page_vars[idx]["next"] = None

    for idx in range(len(book["pages"])):
        template = env.get_template(page_vars[idx]["template"])
        rendered = template.render(**page_vars[idx])
        with open(os.path.join("output", page_vars[idx]["filename"]), "w") as of:
            of.write(rendered)


def new_spinner():
    chars = "|/-\\|/-\\"
    i = 0
    while True:
        yield chars[i]
        i = i + 1 if i < len(chars) - 1 else 0



def main():
    timestamps = {}
    base_dir = "."
    watch_dir = base_dir
    output_dir = os.path.join(base_dir, "output")

    spinner = new_spinner()
    try:
        while True:
            time.sleep(.1)
            sys.stdout.write("  watching " + next(spinner) + " \r")
            sys.stdout.flush()

            regenerate = False
            # TODO: handle file removals
            for directory in os.walk(watch_dir, topdown=True):
                subdirs = directory[1][:]
                directory[1].clear()
                for subdir in subdirs:
                    full_subdir = os.path.join(directory[0], subdir)
                    if not os.path.samefile(full_subdir, output_dir):
                        directory[1].append(subdir)
                for filename in directory[2]:
                    full_path = os.path.join(directory[0], filename)
                    old_last_modified = timestamps.get(full_path, 0)
                    new_last_modified = os.path.getmtime(full_path)
                    if new_last_modified > old_last_modified:
                        timestamps[full_path] = new_last_modified
                        regenerate = True

            if regenerate:
                with open(sys.argv[1], "r") as f:
                    book = yaml.safe_load(f)
                    generate(book)
                    print("\r[{:}] Regenerated book contents".format(datetime.datetime.now().strftime('%I:%M:%S %p')))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
