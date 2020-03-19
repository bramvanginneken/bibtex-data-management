# this file contains functionality to read diag.bib or another bib file and do all sorts of checks and processing, like
# provide overall statistics
# check if key matches year
# check format of key
# check if pdf name matches key
# check if pdf is listed and exists on disc
# extract first page of pdf to see if it is the correct version
# copy diag pdfs to dropbox location, get temp links https://www.dropboxforum.com/t5/API-Support-Feedback/Generate-links-and-passwords-with-Python/td-p/198399
# remove trailing point in title
# add {} around capitalized abbreviations in title
# check if arxiv links are correct
# check if doi is present when it should be and if it resolves
# check if pmids are correct
# retrieve citations via google scholar, using publish or perish lists
# check if strings are used when they should be
# check if strings resolve

import os.path
import csv
from unidecode import unidecode
from pdf2image import convert_from_path

allowed_fields = frozenset(
    ['author', 'title', 'journal', 'year', 'volume', 'issue', 'month', 'pages', 'doi', 'abstract', 'file',
     'optnote', 'pmid', 'gsid', 'gscites', 'booktitle', 'school', 'number', 'url', 'copromotor', 'promotor',
     'publisher', 'series'])

def strip_cb(s):
    '''removes curly braces and white space at begin and end'''
    s = s.strip()
    while len(s) > 0 and s[0] == "{":
        s = s[1:len(s)]
        s = s.strip()
    while len(s) > 0 and s[-1] == "}":
        s = s[0:len(s) - 1]
        s = s.strip()
    return s


def split_strip(s, sep=[',']):
    '''splits the string, removing trailing spaces around every element'''
    s = s.strip()
    t = []
    p = s.find(sep[0])
    while p > -1:
        t.append(s[0:p].strip())
        s = s[p + 1:len(s)]
        p = s.find(sep[0])
    if len(s) > 0:
        t.append(s.strip())
    return t


class BibEntry:

    def __init__(self):
        self.key = ""
        self.type = ""
        self.string = ""
        self.value = ""
        self.pdf = False
        self.line = ""
        self.fields = {}

    def print(self):
        strings = self.to_lines()
        for s in strings:
            print(s)

    def to_lines(self):
        strings = []
        if self.type == "string":
            strings.append('@' + self.type + '{' + self.key + " = " + self.value + '}\n')
        elif self.type == "comment":
            pass
        else:
            strings.append('@' + self.type + '{' + self.key + ",\n")
            for k, v in self.fields.items():
                if k in allowed_fields:
                    value = unidecode(v)
                    strings.append('  ' + k + " = " + value + ",\n")
            strings.append('}\n')
        return strings

    def reformat_optnote(self):
        if self.fields.get('optnote'):
            s = self.fields['optnote']
            s = strip_cb(s)
            s = split_strip(s)
            for i in s:
                i = i.strip()
                i = i.upper()
            s.sort()
            ss = "{"
            for i in s:
                ss += i + ", "
            ss = ss[:-2] + "}"
            self.fields['optnote'] = ss

    def isDIAG(self):
        if not self.fields.get('optnote'):
            return False
        s = self.fields['optnote']
        return s.find("DIAG") != -1

    def getFieldValue(self):
        """
        Eats one field and value from the long line making up the remainder of the bib entry
        """
        i = self.line.find("=")
        if (i < 0):
            return False
        field = self.line[0:i].strip()
        self.line = self.line[i + 1:len(self.line)]
        # do we find first a comma or first a curly brace
        comma = self.line.find(",")
        brace = self.line.find("{")
        if brace > -1 and comma > -1 and brace < comma:
            count = 1
            i = brace + 1
            while count > 0:
                if self.line[i] == "}":
                    count -= 1
                if self.line[i] == "{":
                    count += 1
                i += 1
            self.value = self.line[brace:i].strip()
            self.line = self.line[i + 1:len(self.line)].strip()
        elif comma > -1:
            self.value = self.line[0:comma].strip()
            self.line = self.line[comma + 1:len(self.line)].strip()
        else:
            assert False
        self.fields[field] = self.value
        return True

    def parse(self, lines):
        '''lines makes up all lines of a bib entry'''
        # first turn lines into one long string
        self.line = ''
        for i in range(0, len(lines)):
            self.line += lines[i]
            self.line += ' '
        self.line = self.line.strip()
        if (len(self.line) == 0):
            return

        # find type and key
        assert (self.line[0] == "@")
        i = self.line.find("{")
        assert (i > 1);
        self.type = self.line[1:i].strip().lower()

        # if type is string, we get the string its the value and we're done
        if (self.type == 'string'):
            j = self.line.find("=")
            assert (j > i);
            self.key = self.line[i + 1:j].strip()
            k = self.line.find("}")
            assert (k > j)
            self.value = self.line[j + 1:k].strip()
            return

        # if type is comment, we get the value and we're done
        if (self.type == 'comment'):
            j = self.line.find("}")
            assert (j > i);
            self.value = self.line[i + 1:j].strip()
            return

        # get the key
        j = self.line.find(",")
        assert (j > i)
        self.key = self.line[i + 1:j].strip()
        self.line = self.line[j + 1:len(self.line)].strip()
        assert (self.line[-1] == "}")
        self.line = self.line[:-1] + ",}"  # possibly extra comma, makes sure there is one!

        # next we process the rest of the entry, field by field
        while self.getFieldValue():
            pass

    def check_pdf_exists(self, path):
        fn = path + self.key + '.pdf'
        self.pdf = os.path.isfile(fn)
        return self.pdf


def read_bibfile(filename, entries):
    fp = open(filename, encoding='utf-8')
    line = fp.readline()
    while line and line.find("@") != 0:
        line = fp.readline()  # find first entry
    entry = []
    while line:
        if line.find("@") == 0:  # new entry found
            be = BibEntry()
            be.parse(entry)
            be.reformat_optnote()
            if len(be.key) > 0:
                entries.append(be)
            entry = [line]
        else:
            entry.append(line)
        line = fp.readline()
    # parse the last entry
    be = BibEntry()
    be.parse(entry)
    be.reformat_optnote()
    if len(be.key) > 0:
        entries.append(be)
    fp.close()


def statistics(e):
    print("\nStatistics on entries\n")
    kd = {}
    k = 0
    for i in range(0, len(e)):
        s = e[i].type
        if kd.get(s) == None:
            kd[s] = 1
        else:
            kd[s] = kd[s] + 1
    key_list = kd.keys()
    for key in key_list:
        # print the specific value for the key
        if key != 'string':
            k += kd[key]
        print('key = ' + key + ' value = ' + str(kd[key]))
    print(f"Total entries: {len(e)}. Excluding string: {k}\n")
    print("\nStatistics on fields within entries")
    kd = {}
    for i in range(0, len(e)):
        key_list = e[i].fields.keys()
        for s in key_list:
            if kd.get(s) == None:
                kd[s] = 1
            else:
                kd[s] = kd[s] + 1
    key_list = kd.keys()
    for key in key_list:
        # print the specific value for the key
        print('key = ' + key + ' value = ' + str(kd[key]))


# check if thumbnail (png image of first page of pdf) exists, if not create it
def create_thumb(pdfpath, thumbpath, key):
    pdfname = pdfpath + key + '.pdf'
    thumbname = thumbpath + key + '.png'
    if not os.path.isfile(pdfname):
        print("cannot find pdf file " + pdfname)
        return
    if os.path.isfile(thumbname):
        # thumb already exists, we're done
        return
    print("will create png for " + pdfname)

    images = convert_from_path(pdfname)
    if len(images) > 0:
        images[0].save(thumbname, "PNG")
        print("Wrote " + thumbname)


def check_missing_pdfs(e, addmissingthumbs):
    print("\nPrinting journal/conference article entries (not arXiv) with a missing pdf file:")
    for i in e:
        if i.type == 'article' or i.type == 'inproceedings':
            j = i.fields.get('journal')
            if i.type == 'article' and j == None:
                print(f"No journal field in journal article {i.key}")
            else:
                if j != None and j.find("arXiv") == -1:
                    if i.check_pdf_exists('C:/Users/bramv/literature/pdf/') == False:
                        print(f"Missing pdf for journal article {i.key}")
                    else:
                        if addmissingthumbs:
                            create_thumb('C:/Users/bramv/literature/pdf/',
                                         'C:/Users/bramv/literature/png/publications/', i.key)
                else:
                    if i.check_pdf_exists('C:/Users/bramv/literature/pdf/') == False:
                        print(f"Missing pdf for inproceedings {i.key}")
                    else:
                        if addmissingthumbs:
                            create_thumb('C:/Users/bramv/literature/pdf/',
                                         'C:/Users/bramv/literature/png/publications/', i.key)


def copy_pdf_png(e, source, target):
    print("\nCopying pdf and png:")
    k = 0
    s = 0
    for i in e:
        fn = source + 'pdf/' + i.key + '.pdf'
        if os.path.isfile(fn):
            si = os.path.getsize(fn)
            s += si
            ft = target + 'pdf/' + i.key + '.pdf'
            k += 1
            print(f"Copying file {k}: {fn} of {si} bytes, to {ft}")
    print(f"Total files {k}, tot size {s}")


def read_profiles(profiles):
    for p in profiles:
        with open(p, newline='') as csvfile:
            dialect = csv.Sniffer().sniff(csvfile.read(1024))
            csvfile.seek(0)
            reader = csv.reader(csvfile, dialect)
            reader = csv.DictReader(csvfile, None, None, None, dialect)
            for row in reader:
                gsurl = row['CitesURL']
                i = gsurl.find('&cites=')
                gsid = ''
                if (i > -1):
                    gsid = gsurl[i + 7:len(gsurl)]
                author = row['Authors']
                i = author.find(" ")
                if i > -1:
                    j = author.find(",")
                    if j == -1:
                        j = len(author)
                    author = author[i + 1:j].lower()  # needs more checks
                author = unidecode(author)
                title = row['Title'].lower()
                if len(title) > 40:
                    title = title[0:40]
                print(row['Cites'], "-", gsid, "-", row['Year'], "-", author, title)


def check_trailing_point_titles(entries):
    print("\nTitles with a trailing point:")
    for i in entries:
        title = i.fields.get("title")
        if title == None:
            if i.type != 'string':
                print(f"{i.key} has no title")
        else:
            title = strip_cb(title)
            if title[-1] == ".":
                print(f"{i.key}: {title}")


def check_doi(entries):
    print("\nJournal articles without a doi:")
    for i in entries:
        if i.type == 'article':
            doi = i.fields.get("doi")
            if doi == None:
                journal = i.fields.get("journal")
                year = i.fields.get("year")
                print(f"{i.key} in journal {journal} from year {year} has no doi")
    print("\nConference articles without a doi:")
    for i in entries:
        if i.type == 'inproceedings':
            doi = i.fields.get("doi")
            if doi == None:
                booktitle = i.fields.get("booktitle")
                year = i.fields.get("year")
                print(f"{i.key} in booktitle {booktitle} from year {year} has no doi")


def check_duplicates(entries):
    print("\nCheck possible duplicates:")
    for i in range(len(entries)):
        key1 = strip_cb(entries[i].key).lower()
        for j in range(i + 1, len(entries)):
            key2 = strip_cb(entries[j].key).lower()
            if key1 == key2:
                print("\nPossible duplicate entries " + entries[i].key + " and " + entries[j].key)


def print_all(entries):
    for i in entries:
        i.print()


def save_to_file(entries, fname):
    file = open(fname, 'w')
    for i in entries:
        print(i.key)
        l = i.to_lines()
        if i.type != 'string':
            file.write("\n")
        file.writelines(l)
    file.close()


import dropbox
import datetime


def creating_shared_link_password(dbx, path, password):
    link_settings = dropbox.sharing.SharedLinkSettings(
        requested_visibility=
        dropbox.sharing.RequestedVisibility.password,
        link_password=password,
        expires=datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    )
    link = dbx.sharing_create_shared_link_with_settings(path, settings=link_settings)
    print(link.url)


def testdropbox():
    dbx = dropbox.Dropbox('uQPH-wAJon0AAAAAAAElx9n0cGg0ZDJ7N_28zcowjKGRWDVFwBS4U0wKGvPOPpzs')
    dbx.users_get_current_account()
    # for entry in dbx.files_list_folder('/diag/literature/pdf').entries:
    #    print(entry.name)
    creating_shared_link_password(dbx, '/diag/literature/pdf/Ginn10.pdf', 'prst')


if __name__ == '__main__':

    # read_profiles(["PoPCitesBvG6.csv"])

    entries = []
    read_bibfile('C:/Users/bramv/Dropbox (Personal)/Apps/bibapp/diag/literature/d.bib', entries)

    copy_pdf_png(entries, 'C:/Users/bramv/literature/', 'C:/Users/bramv/Dropbox (Personal)/Apps/bibapp/diag/literature/')

    statistics(entries)
    # check_missing_pdfs(entries, True)
    # check_trailing_point_titles(entries)
    # check_doi(entries)
    # check_duplicates(entries)

    # save_to_file(entries, 'diag-2020.bib')
    # testdropbox()
