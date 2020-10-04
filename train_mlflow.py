import pandas as pd
import numpy as np
import os
from sklearn.naive_bayes import BernoulliNB
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import accuracy_score
import mlflow
from joblib import dump
import typer
import boto3
import logging

logging.basicConfig(level=logging.DEBUG)

train = typer.Typer()


@train.command()
def train(production_ready: bool = False) -> None:
    TRACKING_URI = (
        "http://testuser:test@ec2-3-9-174-162.eu-west-2.compute.amazonaws.com"
    )
    mlflow.set_tracking_uri(TRACKING_URI)
    s3 = boto3.client("s3")
    bucket_name = "workshop-mlflow-artifacts"

    logging.debug("Start downloading training and test data from S3...")
    s3.download_file(bucket_name, "data/train.csv", "train.csv")
    s3.download_file(bucket_name, "data/test.csv", "test.csv")
    logging.debug("Downloaded training and test data from S3!")

    train = pd.read_csv("train.csv", names=["review", "sentiment"])
    test = pd.read_csv("test.csv", names=["review", "sentiment"])
    X_raw_train = train["review"]
    X_raw_test = test["review"]
    y_train = train["sentiment"]
    y_test = test["sentiment"]

    with mlflow.start_run(experiment_id="2"):
        logging.debug(mlflow.get_artifact_uri())

        feature_engineering_params = {"binary": True}
        for k, v in feature_engineering_params.items():
            mlflow.log_param(str(k), str(v))
        feature_engineering = CountVectorizer(**feature_engineering_params)

        classifier_params = {"alpha": 0.5, "binarize": 0.0}
        for k, v in classifier_params.items():
            mlflow.log_param(str(k), str(v))
        classifier = BernoulliNB(**classifier_params)

        logging.debug("Begin training..")
        X_train = feature_engineering.fit_transform(X_raw_train)
        classifier.fit(X_train, y_train)
        y_pred_train = classifier.predict(X_train)
        train_accuracy = accuracy_score(y_train, y_pred_train)
        logging.debug("Done training!")

        X_test = feature_engineering.transform(X_raw_test)
        y_pred_test = classifier.predict(X_test)
        test_accuracy = accuracy_score(y_test, y_pred_test)

        mlflow.log_metric("training accuracy", train_accuracy)
        mlflow.log_metric("test accuracy", test_accuracy)

        logging.debug("Persisting models..")
        dump(feature_engineering, f"{os.getcwd()}/feature_engineering.joblib")
        mlflow.log_artifact(f"{os.getcwd()}/feature_engineering.joblib")

        dump(classifier, f"{os.getcwd()}/classifier.joblib")
        mlflow.log_artifact(f"{os.getcwd()}/classifier.joblib")
        logging.debug("Done persisting models!")

        if production_ready:
            mlflow.set_tag("live", 1)
        else:
            mlflow.set_tag("production_candidate", 1)

        # Cleanup
        os.remove(f"{os.getcwd()}/feature_engineering.joblib")
        os.remove(f"{os.getcwd()}/classifier.joblib")
        os.remove(f"{os.getcwd()}/train.csv")
        os.remove(f"{os.getcwd()}/test.csv")


if __name__ == "__main__":
    train()
