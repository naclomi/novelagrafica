#!/usr/bin/env python3
import jinja2
import yaml
import sys
import copy
import os
import re
import shutil
import time
import traceback
import datetime

def deep_sub(old, new, data):
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = v.replace(old, new)
            else:
                deep_sub(old, new, v)
    elif isinstance(data, list):
        for idx in range(len(data)):
            if isinstance(data[idx], str):
                data[idx] = data[idx].replace(old, new)
            else:
                deep_sub(old, new, data[idx])
    else:
        pass

def generate(book):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('templates/'),
        autoescape=jinja2.select_autoescape()
    )

    shutil.copytree("skeleton", "output", dirs_exist_ok=True)

    pattern_env = jinja2.Environment(
        loader=jinja2.DictLoader(book["patterns"])
    )

    expanded_pages = []
    for idx in range(len(book["pages"])):
        if "range" in book["pages"][idx]:
            range_exp = re.sub("\s", "", book["pages"][idx]["range"])
            range_exp_tokens = re.match("([^:]+):([0-9]+)..([0-9]+)", range_exp)
            var_name = range_exp_tokens.group(1)
            range_start = int(range_exp_tokens.group(2))
            range_end = int(range_exp_tokens.group(3))
            for rep_idx in range(range_start, range_end+1):
                new_page = copy.deepcopy(book["pages"][idx])
                del new_page["range"]
                deep_sub(var_name, str(rep_idx), new_page)
                expanded_pages.append(new_page)
        else:
            expanded_pages.append(book["pages"][idx])
    book["pages"] = expanded_pages

    page_vars = []
    for idx in range(len(book["pages"])):
        page_vars.append(copy.deepcopy(book["base"]))
        page_vars[-1].update(book["pages"][idx])
        for template_name in pattern_env.list_templates():
            if template_name not in book["pages"][idx]:
                page_vars[-1][template_name] = pattern_env.get_template(template_name).render(**page_vars[idx])
        page_vars[-1]["page"] = page_vars[-1]
        page_vars[-1]["all_pages"] = page_vars

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
                try:
                    with open(sys.argv[1], "r") as f:
                        book = yaml.safe_load(f)
                        generate(book)
                        print("\r[{:}] Regenerated book contents".format(datetime.datetime.now().strftime('%I:%M:%S %p')))
                except (jinja2.exceptions.TemplateError, yaml.parser.ParserError) as e:
                    traceback.print_exc()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
