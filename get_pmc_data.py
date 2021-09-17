import argparse
import ijson
import json
import os
import pickle
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from tqdm import tqdm


def from_mesh2id(labels_list, mapping_id):
    mesh_id = []
    for mesh in labels_list:
        index = mapping_id.get(mesh.strip())
        if index is None:
            print(index)
            pass
        else:
            mesh_id.append(index.strip())
    return mesh_id


def get_pmids_from_pmc(filelist):

    """read file list from PMC at ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.txt"""

    pmids = []
    with open(filelist, 'r') as f:
        for line in f:
            info = line.split('\t')
            if len(info) <=3:
                continue
            else:
                pmid = info[3]
                if pmid.startswith('PMID:'):
                    pmid = pmid[5:]
                pmids.append(pmid)
    pmids = list(set(list(filter(None, pmids))))

    return pmids


def get_all_linked_file(url):

    """
    get linked file link list from PubMed Annual Baseline at https://lhncbc.nlm.nih.gov/ii/information/MBR.html

    OR
    use command lines : wget https://lhncbc.nlm.nih.gov/ii/information/MBR/Baselines/2002.html
                        sed -n 's/.*href="\([^"]*\).*/\1/p' 2002.html > file_name.txt
                        wget -i file_name.txt
                        gunzip *.gz
    """

    fp = urllib.request.urlopen(url)
    parser = 'html.parser'
    soup = BeautifulSoup(fp, parser, from_encoding=fp.info().get_param('charset'))

    links = []
    for link in soup.find_all('a', href=True):
        links.append(link)

    return links


def check_if_document_is_mannually_curated(file):
    tree = ET.parse(file)
    root = tree.getroot()
    pmids = []
    for articles in root.findall('PubmedArticle'):
        medlines = articles.find('MedlineCitation')
        if 'IndexingMethod' in medlines.attrib:
            pmid = medlines.find('PMID').text
            # file_name = Path(file).name.strip('.xml')[6:]
            # pmid = file_name[:2] + str(version) + file_name[3:]
            pmids.append(pmid)
        else:
            continue
    pmids = list(set(pmids))
    return pmids


def get_mannually_indexed_pmc(pmid, pmc):
    """
    remove the articles that are automated and curated from the PMC list
    """
    pmids = pickle.load(open(pmid, 'rb'))

    pmcs = []
    with open(pmc, 'r') as f:
        for ids in f:
            pmcs.append(ids.strip())

    diff_pmc = list(set(pmcs) - set(pmids))
    print('number of instance in dataset: %d' % diff_pmc)

    return diff_pmc


def check_if_has_meshID(file):

    tree = ET.parse(file)
    root = tree.getroot()
    pmids_no_mesh = []
    for articles in root.findall('PubmedArticle'):
        medlines = articles.find('MedlineCitation')
        pmid = medlines.find('PMID').text
        if medlines.find('MeshHeadingList') is None:
            pmids_no_mesh.append(pmid)

    print('number of ids without mesh %d' % len(pmids_no_mesh))

    return pmids_no_mesh


def get_data(pmid_path, mapping_path, allMesh):

    pmids = []
    with open(pmid_path, 'r') as f:
        for ids in f:
            pmids.append(ids.strip())

    mapping_id = {}
    with open(mapping_path) as f:
        for line in f:
            (key, value) = line.split('=')
            mapping_id[key] = value

    f = open(allMesh, encoding="utf8", errors='ignore')

    objects = ijson.items(f, 'articles.item')

    dataset = []
    missed_id = []
    for i, obj in enumerate(tqdm(objects)):
        data_point = {}
        ids = obj['pmid']
        if ids in set(pmids):
            try:
                heading = obj['title'].strip()
                heading = heading.translate(str.maketrans('', '', '[]'))
                abstract = obj['abstractText'].strip()
                abstract = abstract.translate(str.maketrans('', '', '[]'))
                if len(heading) == 0 or heading == 'In process':
                    print('paper ', ids, ' does not have title!')
                    continue
                elif len(abstract) == 0:
                    print('paper ', ids, ' does not have abstract!')
                    continue
                else:
                    label = obj["meshMajor"]
                    journal = obj['journal']
                    year = obj['year']
                    data_point['pmid'] = ids
                    data_point['title'] = heading
                    data_point['abstractText'] = abstract
                    data_point['meshMajor'] = label
                    data_point['meshId'] = from_mesh2id(label, mapping_id)
                    data_point['journal'] = journal
                    data_point['year'] = year
                    dataset.append(data_point)
            except AttributeError:
                print(obj["pmid"])
        else:
            missed_id.append(ids)
            continue
    pubmed = {'articles': dataset}
    return pubmed, missed_id


def get_data_from_xml(file, pmc_list):

    tree = ET.parse(file)
    root = tree.getroot()

    dataset = []
    for articles in root.findall('PubmedArticle'):
        data_point = {}
        mesh_ids = []
        mesh_major = []
        medlines = articles.find('MedlineCitation')
        pmid = medlines.find('PMID').text
        article_info = medlines.find('Article')
        if 'IndexingMethod' in medlines.attrib or  medlines.find('MeshHeadingList') is None:
            continue
        elif article_info.find('ArticleTitle') is None or article_info.find('Abstract') is None:
            continue
        elif medlines.find('MeshHeadingList') is None:
            continue
        else:
            title = "".join(article_info.find('ArticleTitle').itertext())
            if title ==  'Not Available' or title == 'In process':
                continue
            elif article_info.find('Abstract').find('AbstractText') is None:
                continue
            elif pmid in set(pmc_list):
                journal_info = article_info.find('Journal')
                year = journal_info.find('JournalIssue').find('PubDate')
                if year.find('Year') is None:
                    year = year.find('MedlineDate').text[:4]
                else:
                    year = year.find('Year').text
                journal_name = journal_info.find('Title').text
                abstract = []
                for ab in article_info.find('Abstract').findall('AbstractText'):
                    abstract.append("".join(ab.itertext()))
                abstract = list(filter(None, abstract))
                abstract = ' '.join(abstract)
                for mesh in medlines.find('MeshHeadingList').findall('MeshHeading'):
                    m = mesh.find('DescriptorName').attrib['UI']
                    m_name = mesh.find('DescriptorName').text
                    mesh_ids.append(m)
                    mesh_major.append(m_name)
                data_point['pmid'] = pmid
                data_point['title'] = title
                data_point['abstractText'] = abstract
                data_point["meshMajor"] = mesh_major
                data_point["meshID"] = mesh_ids
                data_point['journal'] = journal_name
                data_point['year'] = year
                dataset.append(data_point)

    return dataset


def merge_json(file_path):

    results = []
    for root, dirs, files in os.walk(file_path):
        for file in tqdm(files):
            filename, extension = os.path.splitext(file)
            if extension == '.json':
                with open(file, 'rb') as infile:
                    articles = json.load(infile)['articles']
                    articles = list(filter(None, articles))
                    results.extend(articles)

    pubmed = {'articles': results}
    print('number of PMC articles: %d' % len(results))
    return pubmed




def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--path')
    parser.add_argument('--pmids')
    # parser.add_argument('--save')
    # parser.add_argument('--save_no_mesh')
    # parser.add_argument('--pmid_path')
    # parser.add_argument('--mapping_path')
    # parser.add_argument('--allMesh')
    parser.add_argument('--save_dataset')
    # parser.add_argument('--save_missed')

    args = parser.parse_args()

    # pmcs_list = []
    # with open(args.pmids, 'r') as f:
    #     for ids in f:
    #         pmcs_list.append(ids.strip())
    # print('mannually annoted articles: %d' % len(pmcs_list))
    #
    # data = []
    # for root, dirs, files in os.walk(args.path):
    #     for file in tqdm(files):
    #         filename, extension = os.path.splitext(file)
    #         if extension == '.xml':
    #             dataset = get_data_from_xml(file, pmcs_list)
    #             data.extend(dataset)
    # print('Total number of articles %d' % len(data))
    # pubmed = {'articles': data}
    # no_mesh_pmid_list = list(set([ids for pmids in no_mesh for ids in pmids]))
    #
    # new_pmids = list(set(pmids_list) - set(no_mesh_pmid_list))
    # print('Total number of articles %d' % len(new_pmids))
    #
    # pickle.dump(no_mesh_pmid_list, open(args.save_no_mesh, 'wb'))
    # #
    # with open(args.save, 'w') as f:
    #     for ids in new_pmids:
    #         f.write('%s\n' % ids)

    # pubmed, missed_ids = get_data(args.pmid_path, args.mapping_path, args.allMesh)
    #
    pubmed = merge_json(args.path)
    with open(args.save_dataset, "w") as outfile:
        json.dump(pubmed, outfile, indent=4)

    #pickle.dump(missed_ids, open(args.save_missed, 'wb'))


if __name__ == "__main__":
    main()




