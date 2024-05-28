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

class DictWithLinks(dict):
    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)
        self.links = set()

    def addLink(self, k, v):
        self.links.add(k)
        self[k] = v

    def items(self, noLinks=False):
        for item in super().items():
            if not noLinks or item[0] not in self.links:
                yield item

def obj_walk_keys(node, callback, callback_args=[], visited=None):
    if visited is None:
        visited = set()
    if id(node) in visited:
        return
    else:
        visited.add(id(node))
    if isinstance(node, DictWithLinks):
        for k, v in list(node.items(noLinks=True)):
            callback(node, k, v, *callback_args)
            obj_walk_keys(v, callback, callback_args, visited)
    elif isinstance(node, dict):
        for k, v in list(node.items()):
            callback(node, k, v, *callback_args)
            obj_walk_keys(v, callback, callback_args, visited)
    elif isinstance(node, list):
        for idx, elem in enumerate(node):
            obj_walk_keys(elem, callback, callback_args, visited)


def evaluate_inline_templates(obj):
    deepest_level = 0
    def find_max_level(node, k, v):
        nonlocal deepest_level
        deepest_level = max(deepest_level, k.count("?"))
    obj_walk_keys(obj, find_max_level)

    def scrape_patterns(node, k, v, patterns, suffix_re):
        if suffix_re.match(k) and isinstance(v, str):
            patterns[id(node[k])] = v

    def replace_patterns(node, k, v, template_vars, patterns, pattern_env, suffix):
        if id(node[k]) in patterns:
            evaluated_k = k[:-len(suffix)]
            if evaluated_k not in node:
                node[evaluated_k] = pattern_env.get_template(id(node[k])).render(**template_vars)
            del node[k]

    for level in range(1,deepest_level+1):
        patterns = {}

        suffix = "?" * level
        suffix_re = re.compile(r"^[^?]*\?{"+str(level)+r"}$")
        obj_walk_keys(obj, scrape_patterns, (patterns, suffix_re))

        pattern_env = jinja2.Environment(
            loader=jinja2.DictLoader(patterns)
        )

        for page_vars in obj:
            obj_walk_keys(page_vars, replace_patterns, (page_vars, patterns, pattern_env, suffix))



def generate(book, templates_dir, skeleton_dir, output_dir, assets_dir):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_dir),
        autoescape=jinja2.select_autoescape()
    )

    shutil.copytree(skeleton_dir, output_dir, dirs_exist_ok=True)
    if os.path.isdir(assets_dir):
        shutil.copytree(assets_dir, os.path.join(output_dir, "assets"), dirs_exist_ok=True)

    for sequence_name, sequence_pages in book["pages"].items():
        expanded_pages = []
        for idx in range(len(sequence_pages)):
            if "range" in sequence_pages[idx]:
                range_exp = re.sub("\s", "", sequence_pages[idx]["range"])
                range_exp_tokens = re.match("([^:]+):([0-9]+)..([0-9]+)", range_exp)
                var_name = range_exp_tokens.group(1)
                range_start = int(range_exp_tokens.group(2))
                range_end = int(range_exp_tokens.group(3))
                for rep_idx in range(range_start, range_end+1):
                    new_page = copy.deepcopy(sequence_pages[idx])
                    del new_page["range"]
                    new_page[var_name] = str(rep_idx)
                    expanded_pages.append(new_page)
            else:
                expanded_pages.append(sequence_pages[idx])
        book["pages"][sequence_name] = expanded_pages
        sequence_pages = expanded_pages

        for idx, page in enumerate(sequence_pages):
            new_page = DictWithLinks(copy.deepcopy(book["base"]))
            new_page.update(page)
            new_page.addLink("page", new_page)
            new_page.addLink("sequence_name", sequence_name)
            new_page.addLink("sequence_pages", sequence_pages)
            new_page.addLink("sequences", book["pages"])
            sequence_pages[idx] = new_page

        for idx, page in enumerate(sequence_pages):
            page.addLink("first", sequence_pages[0])
            page.addLink("last", sequence_pages[-1])
            if idx > 0:
                page.addLink("prev", sequence_pages[idx-1])
            else:
                page.addLink("prev", None)
            if idx < len(sequence_pages)-1:
                page.addLink("next", sequence_pages[idx+1])
            else:
                page.addLink("next", None)

        evaluate_inline_templates(sequence_pages)

        for page in sequence_pages:
            template = env.get_template(page["template"])
            rendered = template.render(**page)
            with open(os.path.join(output_dir, page["filename"]), "w") as of:
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
                try:
                    with open(args.default_book_yaml, "r") as f:
                        default_book = yaml.safe_load(f)
                    try:
                        schema_filename = os.path.splitext(args.default_book_yaml)
                        schema_filename = ".".join((schema_filename[0], "schema", schema_filename[1][1:]))
                        with open(schema_filename, "r") as f:
                            default_book_schema = yaml.safe_load(f)
                    except FileNotFoundError:
                        default_book_schema = {}
                    with open(args.book_yaml, "r") as f:
                        book = jsonmerge.Merger(default_book_schema).merge(default_book, yaml.safe_load(f))
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
