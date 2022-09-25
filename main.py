import datetime
import os
import re
from stat import S_ISFIFO
import sys
import bs4
from urllib.request import Request, urlopen
from os.path import exists
from shutil import move
import language_tool_python
import argparse
parser = argparse.ArgumentParser()

def spider(prefix, domain, exclude):
    return spider_rec(dict(), prefix, domain, "/", exclude)


def spider_rec(page_texts, prefix, domain, postfix, exclude):
    req = Request(prefix + domain + postfix)
    html_page = urlopen(req)

    soup = bs4.BeautifulSoup(html_page, "lxml")

    page_texts[postfix] = [soup.getText(), soup.find_all('html')[0].get("lang")]
    if page_texts[postfix][1] is None:
        page_texts[postfix][1] = 'en-us'

    for link in soup.findAll('a'):
        href = link.get('href')
        if "mailto:" not in href and (domain in href or href[0] == '/'):
            if href not in page_texts.keys():
                found = False
                for d in exclude:
                    if d in href:
                        found = True
                        break

                if found:
                    continue

                href = href.replace(" ", "%20")
                if domain in href:
                    spider_rec(page_texts, "", "", href, exclude)
                else:
                    spider_rec(page_texts, prefix, domain, href, exclude)

    return page_texts


def split(txt, seps):
    # https://stackoverflow.com/questions/4697006/python-split-string-by-list-of-separators
    default_sep = seps[0]

    # we skip seps[0] because that's the default separator
    for sep in seps[1:]:
        txt = txt.replace(sep, default_sep)
    return [i.strip() for i in txt.split(default_sep)]


def abbrev_num(n):
    abbrevs = ['', 'K', 'M', 'B', 'T', 'Qd', 'Qt', 'Sx']

    zeroes = len(str(n)) - 1
    thous = int(zeroes / 3)
    prefix = n if thous == 0 else int(n / (1000 ** thous))
    abbrev = abbrevs[thous]

    return str(prefix) + abbrev


def main(report: bool):
    if not report:
        print("Reading conf...")

    conf = []
    with open('crawl.conf', 'r') as file:
        for line in file.readlines():
            line = line.replace("\n", "")
            line = line.replace("\r", "")
            conf.append(line)

    domain = conf[1]
    prefix = conf[3]
    ignores = conf[5:conf.index("# Custom Dictionary         Ex: Strato")]
    custDict = conf[conf.index("# Custom Dictionary         Ex: Strato") + 1::]

    if not report:
        print("Crawling site...")
    links = spider(prefix, domain, ignores)
    date = datetime.datetime.utcnow()

    if not report:
        print("Starting local language servers for")
    tools = dict()
    langs = []
    for l in links.keys():
        if links[l][1] not in langs and links[l][1] is not None:
            langs.append(links[l][1])

    for lang in langs:
        if not report:
            print("\t", lang + "...")
        tools[lang] = language_tool_python.LanguageTool(lang)

    if not report:
        print("Spell and grammar checking...")
    links_matched = dict()
    all_matches = 0
    all_filtered_matches = 0
    all_text = 0
    for l in links.keys():
        text = links[l][0].replace('\\r', '\r').replace('\\n', '\n')
        sepLines = [s.strip() for s in re.split("\r\n|\r|\n", text) if s.strip()]
        text = '\n'.join(sepLines)
        all_text += len(text)

        matches = tools[links[l][1]].check(text)
        all_matches += len(matches)
        matches = [match for match in matches if
                   match.context[match.offsetInContext:match.offsetInContext + match.errorLength] not in custDict]
        all_filtered_matches += len(matches)

        if len(matches) > 0:
            links_matched[l] = matches

    if not report:
        print()
    print("Potential errors:", all_matches, "\t", "Errors ignored:", all_matches - all_filtered_matches, "\t",
          "To Fix:", all_filtered_matches)
    print("Pages crawled:", len(links.keys()), "\t", "Pages w/ errors:", len(links_matched), "\t", "Error rate:",
          str(round(len(links_matched) / len(links), 4)))
    print("Words checked:", abbrev_num(all_text), "\t", "Error rate:", str(round(all_filtered_matches / all_text, 4)))

    if S_ISFIFO(os.fstat(0).st_mode) or not sys.stdout.isatty():
        do_colors = False
    else:
        do_colors = True

    for lm in links_matched.keys():
        print(''.join(['='] * 100))
        print(lm)
        print(''.join(['-'] * 100))

        for match in links_matched[lm]:
            print(match.message, "Suggestion:" if len(match.replacements) >= 1 else "",
                  match.replacements[0] if len(match.replacements) >= 1 else "")

            if do_colors:
                print(match.context[:match.offsetInContext] + "\033[91m{}\033[00m".format(
                    match.context[match.offsetInContext:match.offsetInContext + match.errorLength]) + match.context[
                                                                                                      match.offsetInContext + match.errorLength::])
                print()
            else:
                print(match.context)
                print(''.join([' '] * len(match.context[:match.offsetInContext]) + ['^'] * match.errorLength))

        print(''.join(['='] * 100), "\n")

    if not report:
        print("Done.")


parser.add_argument("-r", "--report-only", action='store_true', dest='report', help="Silences status updates")
args = parser.parse_args()

main(args.report)
