#!/usr/bin/env python3
import argparse
import copy
import datetime
import os
import re
import shutil
import sys
import time
import traceback

import jinja2
import jsonmerge
import yaml

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

def generate(book, templates_dir, skeleton_dir, output_dir, assets_dir):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_dir),
        autoescape=jinja2.select_autoescape()
    )

    shutil.copytree(skeleton_dir, output_dir, dirs_exist_ok=True)
    if os.path.isdir(assets_dir):
        shutil.copytree(assets_dir, os.path.join(output_dir, "assets"), dirs_exist_ok=True)

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
        page_vars[-1]["page"] = page_vars[-1]
        page_vars[-1]["all_pages"] = page_vars
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
        with open(os.path.join(output_dir, page_vars[idx]["filename"]), "w") as of:
            of.write(rendered)

    for single_vars in book["singles"]:
        single_vars_base = copy.deepcopy(book["base"])
        single_vars_base.update(single_vars)
        single_vars = single_vars_base
        single_vars["page"] = single_vars
        single_vars["all_pages"] = page_vars
        for template_name in pattern_env.list_templates():
            if template_name not in single_vars:
                single_vars[template_name] = pattern_env.get_template(template_name).render(**single_vars)

        template = env.get_template(single_vars["template"])
        rendered = template.render(**single_vars)
        with open(os.path.join(output_dir, single_vars["filename"]), "w") as of:
            of.write(rendered)


def new_spinner():
    chars = "|/-\\|/-\\"
    i = 0
    while True:
        yield chars[i]
        i = i + 1 if i < len(chars) - 1 else 0

def main():
    sw_base = os.path.dirname(os.path.realpath(__file__))
    parser = argparse.ArgumentParser(prog='novelagrafica')
    parser.add_argument('book_yaml')
    parser.add_argument('-o', '--output-dir', default="./output")
    parser.add_argument('--templates-dir', default=os.path.join(sw_base, "templates"))
    parser.add_argument('--skeleton-dir', default=os.path.join(sw_base, "skeleton"))
    parser.add_argument('--default-book-yaml', default=os.path.join(sw_base, "book.yml"))
    parser.add_argument('--assets-dir', default="./assets")
    parser.add_argument('--watch', action="store_true")

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    timestamps = {}
    watches = [args.templates_dir, args.skeleton_dir, args.assets_dir, args.book_yaml]

    spinner = new_spinner()

    try:
        while True:
            if args.watch:
                time.sleep(.1)
                sys.stdout.write("  watching " + next(spinner) + " \r")
                sys.stdout.flush()

                regenerate = False
                # TODO: handle file removals
                for watch in watches:
                    if os.path.isfile(watch):
                        old_last_modified = timestamps.get(watch, 0)
                        new_last_modified = os.path.getmtime(watch)
                        if new_last_modified > old_last_modified:
                            timestamps[watch] = new_last_modified
                            regenerate = True
                    else:
                        for directory in os.walk(watch, topdown=True):
                            subdirs = directory[1][:]
                            directory[1].clear()
                            for subdir in subdirs:
                                full_subdir = os.path.join(directory[0], subdir)
                                if not os.path.samefile(full_subdir, args.output_dir):
                                    directory[1].append(subdir)
                            for filename in directory[2]:
                                full_path = os.path.join(directory[0], filename)
                                old_last_modified = timestamps.get(full_path, 0)
                                new_last_modified = os.path.getmtime(full_path)
                                if new_last_modified > old_last_modified:
                                    timestamps[full_path] = new_last_modified
                                    regenerate = True
            else:
                regenerate = True

            if regenerate:
                # TODO use jsonmerge.merge to start with base book.yml
                try:
                    with open(args.default_book_yaml, "r") as f:
                        default_book = yaml.safe_load(f)
                    with open(args.book_yaml, "r") as f:
                        book = jsonmerge.merge(default_book, yaml.safe_load(f))
                    generate(book, args.templates_dir, args.skeleton_dir, args.output_dir, args.assets_dir)
                    print("\r[{:}] Regenerated book contents".format(datetime.datetime.now().strftime('%I:%M:%S %p')))
                except (jinja2.exceptions.TemplateError, yaml.parser.ParserError) as e:
                    traceback.print_exc()

            if not args.watch:
                break
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
