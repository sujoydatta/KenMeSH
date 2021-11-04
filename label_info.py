import argparse
import pickle

import ijson
import numpy as np
import torch
from tqdm import tqdm


def label_count(train_data_path):
    # get MeSH in each example
    f = open(train_data_path, encoding="utf8")
    objects = ijson.items(f, 'articles.item')

    label_id = []

    print('Start loading training data')
    for i, obj in enumerate(tqdm(objects)):
        try:
            mesh_id = obj['meshID']
            label_id.append(mesh_id)
        except AttributeError:
            print(obj["pmid"].strip())

    # # get descriptor and MeSH mapped
    # mapping_id = {}
    # with open(MeSH_id_pair_file, 'r') as f:
    #     for line in f:
    #         (key, value) = line.split('=')
    #         mapping_id[key] = value.strip()
    #
    # # count number of nodes and get parent and children edges
    # print('count number of nodes and get edges of the graph')
    # node_count = len(mapping_id)
    # values = list(mapping_id.values())

    class_freq = {}
    for doc in label_id:
        for label in doc:
            # label_id = mapping_id.get(label)
            if label in class_freq:
                class_freq[label] = class_freq[label] + 1
            else:
                class_freq[label] = 1

    train_labels = list(class_freq.keys())
    freq_label = [label for label, freq in class_freq.items() if freq >= 1000]
    # all_meshIDs = list(set([ids for docs in label_id for ids in docs]))

    # missing_mesh = list(set(all_meshIDs) - set(train_labels))

    neg_class_freq = {k: len(label_id) - v for k, v in class_freq.items()}
    save_data = dict(class_freq=class_freq, neg_class_freq=neg_class_freq)

    return save_data, train_labels


def new_label_mapping(train_label, MeSH_id_pair_file, new_mesh_id_path):
    # get MeSH in each example
    # f = open(train_data_path, encoding="utf8")
    # objects = ijson.items(f, 'articles.item')
    #
    # label_id = []
    #
    # print('Start loading training data')
    # for i, obj in enumerate(tqdm(objects)):
    #     try:
    #         mesh_id = obj['meshId']
    #         label_id.append(mesh_id)
    #     except AttributeError:
    #         print(obj["pmid"].strip())
    #
    # flat_label = list(set([m for meshs in label_id for m in meshs]))
    # print('len of mesh', len(flat_label))
    # get descriptor and MeSH mapped
    new_mapping = []
    with open(MeSH_id_pair_file, 'r') as f:
        for line in f:
            (key, value) = line.split('=')
            if value.strip() in train_label:
                new_mapping.append(line)

    # count number of nodes and get parent and children edges
    print('count number of nodes and get edges of the graph %s' % len(new_mapping))
    with open(new_mesh_id_path, 'w') as f:
        for item in new_mapping:
            f.write("%s" % item)

    # class_freq = {}
    # for doc in label_id:
    #     for label in doc:
    #         if label in class_freq:
    #             class_freq[label] = class_freq[label] + 1
    #         else:
    #             class_freq[label] = 1

    # train_labels = list(class_freq.keys())
    # all_meshIDs = list(new_mapping)
    #
    # missing_mesh = list(set(all_meshIDs) - set(train_labels))
    # print('missing_mesh', missing_mesh)

    # neg_class_freq = {k: len(label_id) - v for k, v in class_freq.items()}
    # save_data = dict(class_freq=class_freq, neg_class_freq=neg_class_freq)
    #
    # return save_data


def get_tail_labels(train_data_path):
    # get MeSH in each example
    f = open(train_data_path, encoding="utf8")
    objects = ijson.items(f, 'articles.item')

    label_id = []

    print('Start loading training data')
    for i, obj in enumerate(tqdm(objects)):
        try:
            mesh_id = obj['meshId']
            label_id.append(mesh_id)
        except AttributeError:
            print(obj["pmid"].strip())

    label_sample = {}
    for i, doc in enumerate(label_id):
        for label in doc:
            if label in label_sample:
                label_sample[label].append(i)
            else:
                label_sample[label] = []
                label_sample[label].append(i)

    label_set = list(label_sample.keys())
    num_labels = len(label_set)
    irpl = np.array([len(docs) for docs in list(label_sample.values())])
    irpl = max(irpl) / irpl
    mir = np.average(irpl)
    tail_label = []
    for i, label in enumerate(label_set):
        if irpl[i] > mir:
            tail_label.append(label)

    print('There are total %d tail labels' % len(tail_label))

    return tail_label


def get_label_negative_positive_ratio(train_data_path, MeSH_id_pair_file):

    # get MeSH in each example
    f = open(train_data_path, encoding="utf8")
    objects = ijson.items(f, 'articles.item')

    label_id = []

    print('Start loading training data')
    for i, obj in enumerate(tqdm(objects)):
        try:
            mesh_id = obj['meshId']
            label_id.append(mesh_id)
        except AttributeError:
            print(obj["pmid"].strip())

    mapping_id = {}
    with open(MeSH_id_pair_file, 'r') as f:
        for line in f:
            (key, value) = line.split('=')
            mapping_id[key] = value.strip()

    meshIDs = list(mapping_id.values())
    print('There are %d Meshs' % len(meshIDs))

    label_freq = {}
    for doc in label_id:
        for label in doc:
            if label in label_freq:
                label_freq[label] = label_freq[label] + 1
            else:
                label_freq[label] = 1
    pos = []
    for ids in meshIDs:
        if ids in list(label_freq.keys()):
            pos.append(list(label_freq.values())[list(label_freq.keys()).index(ids)])
        else:
            pos.append(0)

    num_examples = len(label_id)
    pos = np.array(pos)
    print('There are %d lables in total' % np.count_nonzero(pos))
    neg = num_examples - pos
    neg_pos_ratio = neg / pos
    neg_pos_ratio = torch.from_numpy(neg_pos_ratio).type(torch.float)
    return neg_pos_ratio


import string
from nltk.corpus import stopwords
from torchtext.data.utils import get_tokenizer
stop_words = set(stopwords.words('english'))
table = str.maketrans('', '', string.punctuation)


def text_clean(tokens):

    stripped = [w.translate(table) for w in tokens]  # remove punctuation
    clean_tokens = [w for w in stripped if w.isalpha()]  # remove non alphabetic tokens
    text_nostop = [word for word in clean_tokens if word not in stop_words]  # remove stopwords
    filtered_text = [w for w in text_nostop if len(w) > 1]  # remove single character token

    return filtered_text


def get_doc_length(train_data_path):

    tokenizer = get_tokenizer('basic_english')
    # get MeSH in each example
    f = open(train_data_path, encoding="utf8")
    objects = ijson.items(f, 'articles.item')

    text_len = []
    print('Start loading training data')
    for i, obj in enumerate(tqdm(objects)):
        try:
            text = obj['abstractText'].strip()
            text = tokenizer(text)
            length = len(text)
            text_len.append(length)
        except AttributeError:
            print(obj["pmid"].strip())

    a = np.array(text_len)
    print('90% precentile:', np.percentile(a, 90))
    print('95% precentile:',  np.percentile(a, 95))
    print('98% precentile:', np.percentile(a, 98))

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--train')
    parser.add_argument('--meSH_pair_path')
    parser.add_argument('--new_meSH_pair')
    parser.add_argument('--class_freq')

    args = parser.parse_args()

    save_data, train_label = label_count(args.train)
    new_label_mapping(train_label, args.meSH_pair_path, args.new_meSH_pair)
    get_doc_length(args.train)
    # save_data = new_label_mapping(args.train, args.meSH_pair_path, args.new_meSH_pair)
    with open(args.class_freq, 'wb') as f:
        pickle.dump(save_data, f, pickle.HIGHEST_PROTOCOL)
    # tail_labels = get_tail_labels(args.train)
    # pickle.dump(tail_labels, open(args.class_freq, 'wb'))
    # neg_pos_ratio = get_label_negative_positive_ratio(args.train, args.meSH_pair_path)
    # pickle.dump(neg_pos_ratio, open(args.class_freq, 'wb'))
    # percentiles = get_doc_length(args.train)


if __name__ == "__main__":
    main()
