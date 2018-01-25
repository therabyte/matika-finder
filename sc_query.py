# -*- coding: utf-8 -*-

import os
from bs4 import BeautifulSoup
from collections import Counter
import pandas as pd
import re

def text_normalize(input_text):
    return(input_text.lower().replace("\xad", ""))


def parse_html_dom(input_html_content):
    soup = BeautifulSoup(input_html_content, "html5lib")
    document = {}

    paragraphs = []

    for tag in soup.findAll('p'):
        paragraph_entry = {}
        paragraph_entry["text"] = text_normalize(tag.text)
        paragraph_entry["ids"] = []

        #print(tag.renderContents())
        for a in tag.find_all('a'):
            if (a.get('id') is None) or (a.get('class') is None):
                continue
            paragraph_entry["ids"].append({'class': a.get('class'),'id': a.get('id')})

        paragraphs.append(paragraph_entry)

    document["paragraphs"] = paragraphs

    for section in soup.findAll('section'):
        document["class"] = section.get('class')
        document["id"] = section.get('id')

    for h1 in soup.findAll('h1'):
        document["title"] = h1.text

    return(document)


def search_document(query, document):
    _paragraph_results = []

    _document_score = 0
    _document_catch = []
    for paragraph in document["dom"]["paragraphs"]:
        _paragraph_score = 0
        _paragraph_catch = []

        if "keyword_list" in query:
            for kw in query["keyword_list"]:
                if kw in paragraph["text"]:
                    _paragraph_score += 1
                    _document_score += 1
                    _paragraph_catch.append(kw)
                    _document_catch.append(kw)

        elif "alternatives_list" in query:
            for altkw in query["alternatives_list"]:
                for kw in altkw["forms"]:
                    if kw in paragraph["text"]:
                        _paragraph_score += 1
                        _document_score += 1
                        _paragraph_catch.append({"label": altkw["label"], "form" : kw})
                        _document_catch.append({"label": altkw["label"], "form" : kw})

        elif "regex" in query:
            for m in re.finditer(query["regex"], paragraph["text"]):
                _paragraph_score += 1
                _document_score += 1
                if query.get("group_map", None) != None:
                    _catch = {}
                    for k in query["group_map"]:
                        _catch[query["group_map"][k]] = m.group(k)
                else:
                    _catch = { '*' : m.group(0) }
                _paragraph_catch.append(_catch)
                _document_catch.append(_catch)


        if len(_paragraph_catch) > 0:
            _result_entry = {
                "doc_reference" : document["file_absolute_path"],
                "type" : "paragraph",
                "excerpt" : paragraph["text"],
                "score" : _paragraph_score,
                "catch" : _paragraph_catch,
                "ids" : paragraph.get("ids", [])
            }
            _paragraph_results.append(_result_entry)

    results = []
    if _document_score > 0:
        results.append({
                "type" : "document",
                "doc_reference" : document["file_absolute_path"],
                "doc_id" : document["dom"].get("id", "none"),
                "doc_title" : document["dom"].get("title", "no title available"),
                "score" : _document_score,
                "catch" : _document_catch,
                "paragraphs" : _paragraph_results
            })

    return(results)

def search_documentlist(query, doc_list, sort=None):
    results = []
    for doc in doc_list:
        results.extend(search_document(query, doc))

    if sort == "score":
        results = sorted(results, key=lambda el : -el['score'])
    if sort == "catch":
        results = sorted(results, key=lambda el : (-len(set([entry["label"] for entry in el["catch"]])), -el["score"]))

    return(results)


def load_documents(rootdir):
    documents = []

    for root, subFolders, files in os.walk(rootdir):
        #print("{} // {} // {}".format(root,subFolders,files))
        for filename in files:
            if filename.endswith(".html"):
                _html_files_entry = {
                    "relative_root" : root[len(rootdir):],
                    "file_name" : filename,
                    "file_absolute_path" : "{}/{}".format(root,filename)
                }

                with open(_html_files_entry["file_absolute_path"]) as ifile:
                    _html_files_entry["html_content"] = ifile.read()
                _html_files_entry["dom"] = parse_html_dom(_html_files_entry["html_content"])
                documents.append(_html_files_entry)

    return(documents)

def query_keywordlist(kwlist):
    return({
        "keyword_list" : [
            text_normalize(kw) for kw in kwlist
        ]
    })

def query_regex(regex_str, group_map = None):
    return({
        "regex" : regex_str,
        "group_map" : group_map
    })


def transform_excerpt(excerpt, transform_map):
    _output = excerpt
    for k in transform_map:
        _output = _output.replace(k, transform_map[k])

    return(_output)

def result_markdown_formater(query, results):
    _output = []


    if "regex" in query:
        if query.get("group_map", None) == None:
            _output.append("## All occurences\n\n")
            _output.append("| occ | expression |\n| :-- | :-- |\n")
            _catchall = []
            for result in results:
                _catchall.extend([c['*'] for c in result["catch"]])
            _catchall_counter = Counter(_catchall)

            for c in _catchall_counter.most_common():
                _output.append("| {1} | {0} |\n".format(c[0].replace("\n",""), c[1]))
            _output.append("\n\n")

        else:
            for k in query.get("group_map"):
                _groupkey = query["group_map"][k]
                _output.append("## All occurences of group {}\n\n".format(_groupkey))
                _output.append("| occ | expression |\n| :-- | :-- |\n")
                _catchall = []
                for result in results:
                    _catchall.extend([c.get(_groupkey,"_") for c in result["catch"]])
                _catchall_counter = Counter(_catchall)

                for c in _catchall_counter.most_common():
                    _output.append("| {1} | {0} |\n".format(c[0].replace("\n",""), c[1]))

                _output.append("\n\n")


    for result in results:
        _output.append("#### {doc_id} - {title} [[link]({url})]\n".format(
                            doc_id = result.get("doc_id","noid").upper(),
                            title = result.get("doc_title","no title in result"),
                            url = "https://suttacentral.net/pi/{}/".format(result["doc_id"])
                        ))
        _output.append("\n")

        if "keyword_list" in query:
            _output.append("Matches(d={},o={}): ".format(len(set(result["catch"])),
                                                     len(result["catch"])))

            _suboutput = []
            for kw in query["keyword_list"]:
                if kw in result["catch"]:
                    _suboutput.append("[{}]".format(kw))
                else:
                    _suboutput.append("~~[{}]~~".format(kw))
            _output.append(", ".join(_suboutput))

        elif "alternatives_list" in query:
            _output.append("Matches(d={},o={}): ".format(len(set([entry["label"] for entry in result["catch"]])),
                                                     len(result["catch"])))
            _suboutput = []
            _result_labels = [alt["label"] for alt in result["catch"]]
            for altkw in query["alternatives_list"]:
                if altkw["label"] in _result_labels:
                    _suboutput.append("[{}]".format(altkw["label"]))
                else:
                    _suboutput.append("~~[{}]~~".format(altkw["label"]))

            _output.append(", ".join(_suboutput))

        elif "regex" in query:
            _output.append("Matches(o={}): \n".format(len(result["catch"])))
            _catches = Counter([c['*'] for c in result["catch"]])
            for c in _catches:
                _output.append("> [o={1}] {0}\n\n".format(c.replace("\n",""), _catches[c]))

        _output.append("\n")
        _output.append("\n")

        for paragraph in result["paragraphs"]:
            # todo: id
            _output.append("**Paragraph {}**\n> ".format(paragraph["ids"]))
            if "alternatives_list" in query:
                excerpt_transform_map = dict(
                    [(c['form'],"**{}**".format(c['form'])) for c in paragraph['catch']]
                )
            elif "regex" in query:
                excerpt_transform_map = dict(
                    [
                        (c['*'],"**{}**".format(c['*']))
                        for c in paragraph['catch']
                    ]
                )
            else:
                excerpt_transform_map = dict(
                    [(c,"**{}**".format(c)) for c in paragraph['catch']]
                )

            _output.append(transform_excerpt(paragraph["excerpt"], excerpt_transform_map))
            _output.append("\n\n")

        _output.append("\n")

    return("".join(_output))


def collect_matika_cooccurences_counter(results):
    counts = Counter()

    for result in results:
        for paragraph_catch in result["paragraphs"]:
            for k1 in paragraph_catch["catch"]:
                for k2 in paragraph_catch["catch"]:
                    if k2["label"] == k1["label"]:
                        continue
                    counts.update([(k1["label"],k2["label"]), (k2["label"],k1["label"])])
    return(counts)

def collect_matika_cooccurences_pivot(results, transform=None, normalize=None):
    cooccurences = collect_matika_cooccurences_counter(results)

    if transform == None:
        df = pd.DataFrame.from_records([(key[0],key[1],cooccurences[key]) for key in cooccurences],
                                        columns=["word1", "word2", "score"])
    else:
        df = pd.DataFrame.from_records([(key[0],key[1],transform(cooccurences[key])) for key in cooccurences],
                                        columns=["word1", "word2", "score"])

    if normalize == "minmax":
        df['score'] = (df['score'] - df['score'].min()) / (df['score'].max() - df['score'].min())

    return (df.pivot(index="word1",
                     columns="word2",
                     values="score")
                     .fillna(0))

if __name__ == '__main__':
    _rootdir = "/home/datayana/suttacentral-data/text/pi/su"

    _docs = load_documents(_rootdir)
    print("loaded {} files, total bytes {}".format(len(_docs), sum([len(entry["html_content"]) for entry in _docs])))

    _query = query_keywordlist([
                "anussavena", "paramparāya", "itikirāya", "piṭaka­sam­padā­nena",
                "takkahetu", "nayahetu", "ākāra­pari­vitak­kena", "diṭṭhi­nij­jhā­nak­khan­tiyā",
                "bhabbarūpatāya", "samaṇo no garū"
        ])

    _global_results = search_documentlist(_query, _docs, sort="score")
    print("Results found: {}".format(len(_global_results)))

    with open("results-kwlist.md", "w") as ofile:
        ofile.write(result_markdown_formater(_query, _global_results))
