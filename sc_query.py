# -*- coding: utf-8 -*-

import os
from bs4 import BeautifulSoup
from collections import Counter
import pandas as pd
import re


###################
# TEXT PROCESSING #
###################

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


#################
# CORPUS/ENGINE #
#################

class Corpus():
    def __init__(self):
        self.documents = []

    def load_suttacentral(self, rootdir):
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
                    self.documents.append(_html_files_entry)

    def count(self):
        return((len(self.documents), sum([len(entry["html_content"]) for entry in self.documents])))

    def search(self, query, sort=None):
        results = SearchResultList()
        for doc in self.documents:
            s = query.search(doc)
            if s:
                results.append(s)

        results.sort_by(sort)
        return(results)


##################
# SEARCH RESULTS #
##################

class SearchResultList():
    def __init__(self):
        self.results = []

    def sort_by(self, keystr):
        if keystr == 'score':
            self.results = sorted(self.results, key=lambda el : el.score('score'))
        if keystr == 'catch':
            self.results = sorted(self.results, key=lambda el : el.score('catch'))

    def iterate(self):
        for r in self.results:
            yield r

    def append(self, result):

        self.results.append(result)

    def extend(self, resultb):
        self.results.extend(resultb.results)

    def subset(self, id_regexp):
        ret = SearchResultList()
        for result in self.results:
            if re.match(id_regexp, result.id):
                ret.results.append(result)
        return(ret)

    def __len__(self):
        return(len(self.results))


    def get_all_labels(self, group='*'):
        occurences = []

        for result in self.results:
            for c in result.document_catches:
                # label group form
                if c[1] == group:
                    occurences.append(c[0])

        return(Counter(occurences).most_common())


    def get_labels_cooccurences(self, group='*', level='paragraph'):
        counts = Counter()

        for result in self.results:
            for r in result.paragraph_results:
                for k1 in r["catches"]:
                    for k2 in r["catches"]:
                        if k2[0] == k1[0]:
                            continue
                        counts.update([(k1[0],k2[0]), (k2[0],k1[0])])
        return(counts)

    def cooccurence_pivot(self, group='*', level='paragraph', transform=None, normalize=None):
        cooccurences = self.get_labels_cooccurences(group, level)

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


    def get_all_forms(self, group='*'):
        occurences = []

        for result in self.results:
            for c in result.document_catches:
                # label group form
                if c[1] == group:
                    occurences.append(c[2])

        return(Counter(occurences).most_common())

    def get_all_docids(self, group='*'):
        occurences = set()
        for result in self.results:
            occurences.add(result.id)

        return(occurences)


    def get_all_document_catches(self, group='*', discard_forms=False):
        occurences = {}

        for result in self.results:
            for c in result.document_catches:
                # label group form
                if c[1] == group:
                    if discard_forms:
                        _c = (c[0], c[1], None)
                    else:
                        _c = c
                    if _c in occurences:
                        occurences[_c].append(result.id)
                    else:
                        occurences[_c] = [result.id]

        occurence_list = []
        for k in occurences:
            occurence_list.append(
                (len(occurences[k]), occurences[k], k)
            )

        return(sorted(occurence_list, key=lambda x : -x[0]))

    def get_all_paragraph_catches(self, group='*', discard_forms=False):
        occurences = {}

        for result in self.results:
            for paragraph in result.paragraph_results:
                # label group form
                for c in paragraph['catches']:
                    if c[1] == group:
                        if discard_forms:
                            _c = (c[0], c[1], None)
                        else:
                            _c = c
                        if _c in occurences:
                            occurences[_c].append( (result.id, paragraph.get('ids',None)) )
                        else:
                            occurences[_c] = [(result.id, paragraph.get('ids',None))]

        occurence_list = []
        for k in occurences:
            occurence_list.append(
                (len(occurences[k]), occurences[k], k)
            )

        return(sorted(occurence_list, key=lambda x : -x[0]))


class SearchResult():
    def __init__(self, document):
        self.type = "document"
        self.doc_reference = document["file_absolute_path"]
        self.id = document["dom"].get("id", "none")
        self.doc_title = document["dom"].get("title", "no title available")
        self.document_score = 0
        self.document_catches = []
        self.paragraph_results = []

    def score(self, which):
        return self.document_score
        #elif which == 'catch':
        #    return (-len(set([entry["label"] for entry in el["catch"]])), -el["score"])

    def add_document_catch(self, document, catch):
        self.document_score += 1
        self.document_catches.append(catch)

    def add_paragraph_catch(self, document, paragraph, catch):
        self.add_document_catch(document, catch)
        if len(self.paragraph_results) == 0:
            pc = {
                        "doc_reference" : document["file_absolute_path"],
                        "type" : "paragraph",
                        "excerpt" : paragraph["text"],
                        "catches" : [catch],
                        "ids" : paragraph.get("ids", [])
            }
        else:
            if self.paragraph_results[-1]['ids'] == paragraph['ids']:
                pc = self.paragraph_results.pop()
                pc['catches'].append(catch)
            else:
                pc = {
                            "doc_reference" : document["file_absolute_path"],
                            "type" : "paragraph",
                            "excerpt" : paragraph["text"],
                            "catches" : [catch],
                            "ids" : paragraph.get("ids", [])
                }

        self.paragraph_results.append(pc)

    def close(self):
        if self.document_score > 0:
            return self
        else:
            return None


###########
# QUERIES #
###########

class QueryWordList():
    def __init__(self, kwlist):
        self.keyword_list = [ text_normalize(kw) for kw in kwlist ]

    def _catch(self, kw):
        # label group form
        return( (kw, '*', kw) )

    def search(self, document):
        result = SearchResult(document)

        for paragraph in document["dom"]["paragraphs"]:
            for kw in self.keyword_list:
                if kw in paragraph["text"]:
                    result.add_paragraph_catch(document, paragraph, self._catch(kw))

        return result.close()   # returns None if nothing caught


class QueryAlternatives():
    def __init__(self):
        self.alternatives_list = []

    def add_alternative(self, label, forms):
        self.alternatives_list.append( {"label": label, "forms": forms} )

    def _catch(self, label, form):
        # label group form
        return( (label, '*', form) )

    def search(self, document):
        result = SearchResult(document)

        for paragraph in document["dom"]["paragraphs"]:
            for altkw in self.alternatives_list:
                for kw in altkw["forms"]:
                    if kw in paragraph["text"]:
                        result.add_paragraph_catch(document, paragraph, self._catch(altkw["label"], kw))

        return result.close()   # returns None if nothing caught


class QueryRegex():
    def __init__(self, regex, group_map=None):
        self.regex = regex
        self.group_map = group_map

    def _catch(self, label, group, form):
        # label group form
        return( (label, group, form) )

    def search(self, document):
        result = SearchResult(document)

        for paragraph in document["dom"]["paragraphs"]:
            for m in re.finditer(self.regex, paragraph["text"]):
                if self.group_map == None:
                    result.add_paragraph_catch(document, paragraph, self._catch(m.group(0), '*', m.group(0)))
                else:
                    for k in self.group_map:
                        result.add_paragraph_catch(document, paragraph, self._catch(m.group(k), self.group_map[k], m.group(k)))

        return result.close()   # returns None if nothing caught



###########
# DISPLAY #
###########

def transform_excerpt(excerpt, transform_map):
    _output = excerpt
    for k in transform_map:
        _output = _output.replace(k, transform_map[k])

    return(_output)


class MarkdownFormater():
    def __init__(self):
        self.output = []
        self.line_delimiter = ""

    def occurence_table(self, occurence_list, title):
        self.output.append("## {}\n\n".format(title))
        self.output.append("| occ | expression |\n| :-- | :-- |\n")
        for o in occurence_list:
            # occ, list of references, catch
            self.output.append("| {occ} | {exp} | \n".format(  occ=o[1],
                                                                exp=o[0].replace("\n","")
                                                            ))
        self.output.append("\n")

    def catches_table(self, catches_array, title):
        self.output.append("## {}\n\n".format(title))
        self.output.append("| occ | expression | refs |\n| :-- | :-- | :-- |\n")
        for o in catches_array:
            # occ, list of references, catch
            self.output.append("| {occ} | {exp} | {refs} |\n".format(  occ=o[0],
                                                                       refs=", ".join(o[1]),
                                                                       exp=o[2][2].replace("\n","")
                                                                    ))
        self.output.append("\n")

    def generate(self):
        return(self.line_delimiter.join(self.output))



def result_markdown_formater(query, results):
    _output = []


    if "regex" in query:
        if query.get("group_map", None) == None:
            _output.append("## All occurences\n\n")
            _output.append("| occ | expression | refs |\n| :-- | :-- | :-- |\n")
            _catchall_counter = compute_array_occurences(results, '*')

            for ctuple in _catchall_counter:
                _output.append("| {0} | {2} | {1} |\n".format(c[0], ", ".join(c[1]), c[2].replace("\n","")))
            _output.append("\n\n")

        else:
            for k in query.get("group_map"):
                _groupkey = query["group_map"][k]
                _output.append("## All occurences of group {}\n\n".format(_groupkey))
                _output.append("| occ | expression | refs |\n| :-- | :-- | :-- |\n")

                _catchall_counter = compute_array_occurences(results, _groupkey)
                for c in _catchall_counter:
                    _output.append("| {0} | {2} | {1} |\n".format(c[0], ", ".join(c[1]), c[2].replace("\n","")))

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
