"""
Pre-defined procedures for running rnn, evaluating and recording
"""


import os

import tensorflow as tf

from rnnvis.rnn.config_utils import RNNConfig, TrainConfig
from rnnvis.rnn.command_utils import data_type, pick_gpu_lowest_memory
from rnnvis.rnn.rnn import RNN
from rnnvis.datasets.data_utils import load_data_as_ids, get_lm_data_producer, get_sp_data_producer
from rnnvis.db import get_dataset, NoDataError


def init_tf_environ(gpu_num=0):
    """
    Init CUDA environments, which the number of gpu to use
    :param gpu_num:
    :return:
    """
    if gpu_num == 0:
        cuda_devices = ""
        print("Not using any gpu devices.")
    else:
        try:
            best_gpus = pick_gpu_lowest_memory(gpu_num)
            cuda_devices = ",".join([str(e) for e in best_gpus])
        except:
            raise ValueError("Cannot find gpu devices!")
        print("Using gpu device: {:s}".format(cuda_devices))
    os.environ["CUDA_VISIBLE_DEVICES"] = cuda_devices
    # if FLAGS.gpu_num == 0 else "0,1,2,3"[:(FLAGS.gpu_num * 2 - 1)]


def build_rnn(rnn_config):
    """
    Build an instance of RNN from config
    :param rnn_config: a RNNConfig instance
    :return: a compiled model
    """
    assert isinstance(rnn_config, RNNConfig)
    try:
        word_to_id = get_dataset(rnn_config.dataset, ['word_to_id'])['word_to_id']
    except:
        raise NoDataError
    _rnn = RNN(rnn_config.name, rnn_config.initializer, graph=tf.Graph(), word_to_id=word_to_id)
    _rnn.set_input([None], rnn_config.input_dtype, rnn_config.vocab_size, rnn_config.embedding_size)
    for cell in rnn_config.cells:
        _rnn.add_cell(rnn_config.cell, **cell)
    _rnn.set_output([None, rnn_config.vocab_size], data_type(), rnn_config.use_last_output)
    _rnn.set_target([None], rnn_config.target_dtype, rnn_config.target_size)
    _rnn.set_loss_func(rnn_config.loss_func)
    _rnn.compile()
    return _rnn


def build_trainer(rnn_, train_config):
    """
    Add a trainer to an already compiled RNN instance
    :param rnn_: the already compiled RNN
    :param train_config: a TrainConfig instance
    :return: the rnn_ with trainer added
    """
    assert isinstance(rnn_, RNN)
    assert isinstance(train_config, TrainConfig)
    rnn_.add_trainer(train_config.batch_size, train_config.num_steps, train_config.keep_prob, train_config.optimizer,
                     train_config.lr, train_config.clipper)
    rnn_.add_validator(train_config.batch_size, train_config.num_steps)


def build_model(config, train=True):
    """
    A helper function that wraps build_rnn and build_train to build a model
    :param config:
    :param train:
    :return:
    """
    print("Building model from {:s}".format(config))
    if isinstance(config, str):
        rnn_config = RNNConfig.load(config)
        train_config = TrainConfig.load(config)
    elif isinstance(config, dict):
        rnn_config = config['model']
        train_config = config['train']
    else:
        raise TypeError('config should be a file_path or a dict!')
    rnn_ = build_rnn(rnn_config)
    if train:
        build_trainer(rnn_, train_config)
    setattr(train_config, 'dataset', rnn_config.dataset)
    return rnn_, train_config


def pour_data(dataset, fields, batch_size, num_steps, max_length=None):
    """
    Get data feeders from db
    :param dataset: name of the dataset
    :param fields: fields e.g.: train, valid, test
    :param batch_size:
    :param num_steps
    :return:
    """
    datasets = get_dataset(dataset, fields)
    if datasets is None:
        raise EnvironmentError("Cannot get datasets named {:s}".format(dataset))
    producers = []
    for field in fields:
        data = datasets[field]
        if datasets['type'] == 'sp':  # sp
            producers.append(get_sp_data_producer(data['data'], data['label'], batch_size,
                                                  num_steps if max_length is None else max_length, num_steps))
        elif datasets['type'] == 'lm':
            producers.append(get_lm_data_producer(data['data'], batch_size, num_steps))
        else:
            raise ValueError("Unknown dataset type!")
    return producers


def produce_data(data_paths, train_config):
    train_steps = train_config.num_steps
    batch_size = train_config.batch_size

    data_list, word_to_id, id_to_word = load_data_as_ids(data_paths)
    producers = []
    for data in data_list:
        producers.append(get_lm_data_producer(data, batch_size, train_steps))
    return producers


def produce_ptb_data(data_path, train_config, valid=True, test=True):
    train_path = os.path.join(data_path, "ptb.train.txt")
    valid_path = os.path.join(data_path, "ptb.valid.txt")
    test_path = os.path.join(data_path, "ptb.test.txt")
    paths = [train_path]
    if valid: paths.append(valid_path)
    if test: paths.append(test_path)
    producers = produce_data(paths, train_config)
    return producers


