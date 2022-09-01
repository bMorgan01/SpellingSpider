import datetime
import os

import bs4
from urllib.request import Request, urlopen
from os.path import exists
from shutil import move
import language_tool_python
tool = language_tool_python.LanguageTool('en-US')


def spider(prefix, domain, exclude):
    return spider_rec(dict(), prefix, domain, "/", exclude)


def spider_rec(links, prefix, domain, postfix, exclude):
    req = Request(prefix + domain + postfix)
    html_page = urlopen(req)

    soup = bs4.BeautifulSoup(html_page, "lxml")

    links[postfix] = soup.getText()
    for link in soup.findAll('a'):
        href = link.get('href')
        if "mailto:" not in href and (domain in href or href[0] == '/'):
            if href not in links.keys():
                found = False
                for d in exclude:
                    if d in href:
                        found = True
                        break

                if found:
                    continue

                href = href.replace(" ", "%20")
                if domain in href:
                    spider_rec(links, "", "", href, exclude)
                else:
                    spider_rec(links, prefix, domain, href, exclude)

    return links


def cmp(p1, p2):
    with open(p1, 'r') as f1:
        with open(p2, 'r') as f2:
            l1 = f1.readlines()
            l2 = f2.readlines()
            not_matched = []

            if len(l1) == len(l2):
                for i in range(len(l1)):
                    if l1[i] != l2[i]:
                        return False
            else:
                return False

    return True


def main():
    print("Reading conf...")

    conf = []
    with open('crawl.conf', 'r') as file:
        for line in file.readlines():
            if line[0] != '#':
                line = line.replace("\n", "")
                line = line.replace("\r", "")
                conf.append(line)

    domain = conf[0]
    prefix = conf[1]
    path = conf[2]

    ignores = conf[3::]

    print("Crawling site...")
    links = spider(prefix, domain, ignores)
    date = datetime.datetime.utcnow()

    existed = exists(path)
    oldpath = path
    if existed:
        print("Report already exists, creating temp...")
        path = "newReport.txt"

    # print("Writing to target file...")
    # out = open(path, 'w')
    # out.write("\tSpelling Spider by Ben Morgan - www.benrmorgan.com\n\n")

    for l in links.keys():
        strippedLines = [s.strip() for s in links[l].split('\r\n') if s.strip()]
        strippedLines += [s.strip() for s in links[l].split('\n') if s.strip()]
        uniqueLines = []
        for line in strippedLines:
            if line not in uniqueLines:
                uniqueLines.append(line)

        text = os.linesep.join(uniqueLines)
        matches = tool.check(text)
        print(matches)

        for match in matches:
            print(match.message)
            print(match.context[:match.offsetInContext-1] + "\033[91m {}\033[00m" .format(match.context[match.offsetInContext:match.offsetInContext+match.errorLength]) + match.context[match.offsetInContext+match.errorLength::])

    # if existed and not cmp(oldpath, path):
    #     print("Creating old report backup...")
    #     move(oldpath, oldpath + "-old")
    #     print("Overwriting old report with new one...")
    #     move(path, oldpath)
    # elif existed:
    #     print("Reports are the same, removing temp...")
    #     os.remove(path)

    print("Done.")

main()