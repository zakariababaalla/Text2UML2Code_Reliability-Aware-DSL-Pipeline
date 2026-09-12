import torch
from transformers import BertTokenizerFast, BertForTokenClassification, Trainer, TrainingArguments
from datasets import Dataset
from evaluate import load

# Function to load dataset from TXT
def load_dataset_from_txt(file_path):
    texts = []
    labels = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        tokens = []
        ner_tags = []
        
        for line in f:
            if line.strip() == "":  # Phrase separation
                if tokens:
                    texts.append(tokens)
                    labels.append(ner_tags)
                    tokens = []
                    ner_tags = []
            else:
                word, label = line.strip().split()  # Separate token and label
                tokens.append(word)
                ner_tags.append(label)
        
        if tokens:
            texts.append(tokens)
            labels.append(ner_tags)
    
    return texts, labels


# Function to load annotated dataset from TXT file
def load_annotated_dataset_from_txt(file_path):
    texts, labels = load_dataset_from_txt(file_path)

    # Updated label set to include inheritance relationship
    unique_labels = [
        "O", 
        "B_CLASS_SOURCE", "I_CLASS_SOURCE",
        "B_CLASS_TARGET", "I_CLASS_TARGET",
        "B_ATTRIBUTE", "I_ATTRIBUTE",
        "B_METHOD", "I_METHOD",
        "B_ASSOCIATION", "I_ASSOCIATION",
        "B_AGGREGATION", "I_AGGREGATION",
        "B_COMPOSITION", "I_COMPOSITION",
        "B_INHERITANCE", "I_INHERITANCE"
    ]

    # Map labels to IDs
    label2id = {label: i for i, label in enumerate(unique_labels)}
    id2label = {i: label for i, label in enumerate(unique_labels)}

    # Convert labels to IDs
    ner_tags = [[label2id[label] for label in label_list] for label_list in labels]

    # Create Hugging Face dataset
    dataset = Dataset.from_dict({"tokens": texts, "ner_tags": ner_tags})

    return dataset, label2id, id2label


# Load dataset from the TXT file
file_path = "dataset.txt"
dataset, label2id, id2label = load_annotated_dataset_from_txt(file_path)

# Load BERT tokenizer
tokenizer = BertTokenizerFast.from_pretrained('bert-base-cased')

# Tokenize inputs and align labels with sub-tokens
def tokenize_and_align_labels(examples):
    tokenized_inputs = tokenizer(examples["tokens"], truncation=True, padding=True, is_split_into_words=True)

    labels = []
    for i, label in enumerate(examples["ner_tags"]):
        word_ids = tokenized_inputs.word_ids(batch_index=i)
        
        previous_word_idx = None
        label_ids = []
        for word_idx in word_ids:  
            if word_idx is None:
                label_ids.append(-100)
            elif word_idx != previous_word_idx:  
                label_ids.append(label[word_idx])
            else:
                label_ids.append(-100)
            previous_word_idx = word_idx
        
        labels.append(label_ids)

    tokenized_inputs["labels"] = labels
    return tokenized_inputs

# Apply tokenization and label alignment
try:
    tokenized_dataset = dataset.map(tokenize_and_align_labels, batched=True)
    print("Tokenization completed successfully.")
except Exception as e:
    print(f"Error during tokenization: {e}")
    tokenized_dataset = None

if tokenized_dataset is None:
    raise ValueError("Tokenization failed, please check the dataset or tokenization function.")
else:
    model = BertForTokenClassification.from_pretrained('bert-base-cased', num_labels=len(label2id), id2label=id2label, label2id=label2id)

    # Training arguments
    training_args = TrainingArguments(
        output_dir="./results",
        eval_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=25,
        weight_decay=0.01,
        logging_dir='./logs',
        logging_steps=10,
        save_total_limit=2,
        save_steps=1000,
    )

    metric = load("seqeval")

    def compute_metrics(p):
        predictions, labels = p
        predictions = torch.argmax(torch.tensor(predictions), dim=2).numpy()

        true_labels = [[id2label[l] for l in label if l != -100] for label in labels]
        true_predictions = [[id2label[pred] for pred, label in zip(prediction, label) if label != -100]
                            for prediction, label in zip(predictions, labels)]

        results = metric.compute(predictions=true_predictions, references=true_labels)
        return {
            "precision": results["overall_precision"],
            "recall": results["overall_recall"],
            "f1": results["overall_f1"],
            "accuracy": results["overall_accuracy"],
        }

    # Create Trainer object
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        eval_dataset=tokenized_dataset,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics
    )

    # Train the model
    trainer.train()

    # Save fine-tuned model and tokenizer
    model.save_pretrained('./my-finetuned-model')
    tokenizer.save_pretrained('./my-finetuned-model')

    print("Model and tokenizer saved successfully!")

    # Evaluate the model
    results = trainer.evaluate()
    print("Evaluation results:", results)
