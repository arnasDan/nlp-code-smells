import json
import torch
import os
import numpy as np
from pathlib import Path
from sklearn.utils import shuffle
from transformers import Trainer, TrainingArguments, AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import accuracy_score, recall_score, precision_score, f1_score

root = os.getcwd()
data_directory = root + '/test/'
model_directory = root + '/testable_models/'

class SmellDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

def batch(texts, labels, n=1):
    l = len(texts)
    for idx in range(0, l, n):
        top_bound = min(idx + n, l)
        yield (texts[idx:top_bound], labels[idx:top_bound])

def compute_metrics(p):    
    pred, labels = p
    pred = np.argmax(pred, axis=1)
    accuracy = accuracy_score(y_true=labels, y_pred=pred)
    recall = recall_score(y_true=labels, y_pred=pred)
    precision = precision_score(y_true=labels, y_pred=pred)
    f1 = f1_score(y_true=labels, y_pred=pred)
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1} 

def read_data(smell):
    texts = None
    labels = None
    with open(data_directory + smell + '.texts', 'r') as texts_file:
        texts = json.loads(texts_file.read())
    with open(data_directory + smell + '.labels', 'r') as labels_file:
        labels = json.loads(labels_file.read())
    return texts, labels

smells = [
    'Magic Number',
    'Complex Method',
    'Multifaceted Abstraction',
    'Empty catch clause'
]

def get_metrics(true_positives, true_negatives, false_positives, false_negatives):
    precision = true_positives/(true_positives + false_positives) if true_positives + false_positives > 0 else 0
    recall = true_positives/(true_positives + false_negatives) if true_positives + false_negatives > 0 else 0
    accuracy = (true_positives + true_negatives)/(true_positives + true_negatives + false_positives + false_negatives)
    f1 = 2*((precision * recall)/(precision + recall)) if precision + recall > 0 else 0

    return precision, recall, accuracy, f1

retry = True
model_path = Path(model_directory)
while retry:
    retry = False
    for dir in os.listdir(model_directory):
        smell = dir.split('_')[0]

        print(dir)
        print(smell)
        if smell not in smells:
            print('Unrecognized smell: ' + smell)
            continue

        result_path = (model_path/dir/'result.txt')

        if os.path.exists(result_path):
            print('Already processed: ' + dir)
            continue

        retry = True

        print('Reading data for {}...'.format(smell))
        texts, labels = read_data(smell)

        tokenizer = AutoTokenizer.from_pretrained((model_path/dir), use_fast=True)
        model = AutoModelForSequenceClassification.from_pretrained((model_path/dir))
        model.cuda()
        model.eval()
        
        print('Shuffling...')
        texts, labels = shuffle(texts, labels)

        texts = texts
        labels = labels
        print(len(texts))

        encodings = tokenizer(texts, truncation=True)

        dataset = SmellDataset(encodings, labels)

        args = TrainingArguments(
            per_device_eval_batch_size=11,
            metric_for_best_model='f1',
            output_dir=(model_path/dir/'output'),
            logging_dir=(model_path/dir/'logs')
        )
        trainer = Trainer(
            model=model,
            tokenizer=tokenizer,
            compute_metrics=compute_metrics,
            args=args
        )

        print('Evaluating...')

        result = trainer.predict(dataset)

        print(result)

        with open(result_path, 'w') as texts_file:
            texts_file.write(str(result))
