
import argparse
import zipfile
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def build_features(archive, output, cutoff, workdir):
    archive = Path(archive).resolve()
    output = Path(output).resolve()
    workdir = Path(workdir).resolve()

    if not archive.is_file():
        raise FileNotFoundError(archive)

    if output.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing output: {output}"
        )

    workdir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive) as z:
        for name in ["ml-25m/ratings.csv", "ml-25m/movies.csv"]:
            destination = workdir / name

            if not destination.is_file():
                z.extract(name, workdir)

    spark = (
        SparkSession.builder
        .appName("AIML03_Reproducible_Feature_Engineering")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )

    try:
        ratings = (
            spark.read
            .option("header", True)
            .option("inferSchema", True)
            .csv(str(workdir / "ml-25m/ratings.csv"))
            .select(
                F.col("userId").cast("int"),
                F.col("movieId").cast("int"),
                F.col("rating").cast("double"),
                F.col("timestamp").cast("long")
            )
            .filter(F.col("timestamp") <= cutoff)
            .cache()
        )

        movies = (
            spark.read
            .option("header", True)
            .option("inferSchema", True)
            .csv(str(workdir / "ml-25m/movies.csv"))
            .select(
                F.col("movieId").cast("int"),
                "title",
                "genres"
            )
            .withColumn(
                "genre_list",
                F.split(F.col("genres"), r"\|")
            )
            .cache()
        )

        user_features = ratings.groupBy("userId").agg(
            F.count("*").alias("total_ratings"),
            F.avg("rating").alias("avg_rating"),
            F.max("timestamp").alias("last_rating_timestamp")
        )

        movie_features = ratings.groupBy("movieId").agg(
            F.count("*").alias("rating_count"),
            F.avg("rating").alias("avg_rating")
        )

        movie_catalog = (
            movies.join(movie_features, "movieId", "left")
            .fillna({"rating_count": 0})
        )

        user_genre_features = (
            ratings.join(
                movies.select("movieId", "genre_list"),
                "movieId",
                "inner"
            )
            .withColumn("genre", F.explode("genre_list"))
            .filter(F.col("genre") != "(no genres listed)")
            .groupBy("userId", "genre")
            .agg(
                F.count("*").alias("genre_rating_count"),
                F.avg("rating").alias("genre_avg_rating")
            )
        )

        popularity = (
            movie_catalog
            .filter(F.col("rating_count") >= 100)
            .withColumn(
                "popularity_score",
                F.log1p("rating_count") * F.col("avg_rating")
            )
            .select(
                "movieId",
                "title",
                "rating_count",
                "avg_rating",
                "popularity_score"
            )
        )

        datasets = {
            "movie_features": movie_features,
            "user_features": user_features,
            "movie_catalog": movie_catalog,
            "user_genre_features": user_genre_features,
            "popularity_baseline": popularity
        }

        output.mkdir(parents=True, exist_ok=False)

        for name, dataframe in datasets.items():
            destination = output / name
            dataframe.write.mode("errorifexists").parquet(
                str(destination)
            )
            print(name, "rows:", dataframe.count(), flush=True)

        print("SPARK FEATURE GENERATION COMPLETE", flush=True)

    finally:
        spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--archive", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workdir", default="/content/aiml03_spark_input")
    parser.add_argument(
        "--cutoff",
        type=int,
        default=1466837397
    )

    args = parser.parse_args()

    build_features(
        archive=args.archive,
        output=args.output,
        cutoff=args.cutoff,
        workdir=args.workdir
    )
