import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F


args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "RAW_PATH", "FEATURES_PATH"],
)

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session

job = Job(glue_context)
job.init(args["JOB_NAME"], args)

raw_path = args["RAW_PATH"]
features_path = args["FEATURES_PATH"]


# ---------------------------------------------------------
# 1. Read raw streaming events
# ---------------------------------------------------------

events = spark.read.json(raw_path)


# ---------------------------------------------------------
# 2. Clean and validate events
# ---------------------------------------------------------

events = (
    events
    .filter(F.col("user_id").isNotNull())
    .filter(F.col("product_id").isNotNull())
    .filter(F.col("event_type").isNotNull())
    .filter(F.col("category").isNotNull())
    .filter(F.col("price").isNotNull())
    .withColumn("timestamp", F.to_timestamp("timestamp"))
    .filter(F.col("timestamp").isNotNull())
)


# ---------------------------------------------------------
# 3. Create event-level signals
# ---------------------------------------------------------

events = (
    events
    .withColumn(
        "view_count",
        F.when(F.col("event_type") == "view", 1).otherwise(0),
    )
    .withColumn(
        "cart_count",
        F.when(F.col("event_type") == "add_to_cart", 1).otherwise(0),
    )
    .withColumn(
        "purchase_count",
        F.when(F.col("event_type") == "purchase", 1).otherwise(0),
    )
)


# ---------------------------------------------------------
# 4. Build user × product interaction features
# ---------------------------------------------------------

interactions = (
    events
    .groupBy(
        "user_id",
        "product_id",
        "category",
    )
    .agg(
        F.sum("view_count").alias("views"),
        F.sum("cart_count").alias("cart_adds"),
        F.sum("purchase_count").alias("purchases"),
        F.max("timestamp").alias("last_interaction"),
    )
)


# ---------------------------------------------------------
# 5. Create weighted implicit-feedback score
#
# Views       = 1 point
# Cart adds   = 3 points
# Purchases   = 5 points
# ---------------------------------------------------------

interactions = interactions.withColumn(
    "interaction_score",
    (
        F.col("views") * 1
        + F.col("cart_adds") * 3
        + F.col("purchases") * 5
    ),
)


# ---------------------------------------------------------
# 6. Create user-level behavioral features
# ---------------------------------------------------------

user_features = (
    events
    .groupBy("user_id")
    .agg(
        F.sum("view_count").alias("total_views"),
        F.sum("cart_count").alias("total_cart_adds"),
        F.sum("purchase_count").alias("total_purchases"),
        F.sum(
            F.when(
                F.col("event_type") == "purchase",
                F.col("price"),
            ).otherwise(0)
        ).alias("total_purchase_value"),
        F.avg(
            F.when(
                F.col("event_type") == "purchase",
                F.col("price"),
            )
        ).alias("avg_purchase_price"),
        F.countDistinct("product_id").alias("unique_products_interacted"),
        F.countDistinct("category").alias("unique_categories_interacted"),
        F.max("timestamp").alias("last_activity"),
    )
)


# ---------------------------------------------------------
# 7. Additional user behavioral metrics
# ---------------------------------------------------------

user_features = (
    user_features
    .withColumn(
        "purchase_rate",
        F.when(
            F.col("total_views") > 0,
            F.col("total_purchases") / F.col("total_views"),
        ).otherwise(0.0),
    )
    .withColumn(
        "cart_rate",
        F.when(
            F.col("total_views") > 0,
            F.col("total_cart_adds") / F.col("total_views"),
        ).otherwise(0.0),
    )
    .withColumn(
        "days_since_activity",
        F.datediff(
            F.current_date(),
            F.to_date("last_activity"),
        ),
    )
)


# ---------------------------------------------------------
# 8. Write user features
# ---------------------------------------------------------

(
    user_features
    .write
    .mode("overwrite")
    .parquet(f"{features_path}/user_features/")
)


# ---------------------------------------------------------
# 9. Write recommendation interaction features
# ---------------------------------------------------------

(
    interactions
    .write
    .mode("overwrite")
    .parquet(f"{features_path}/interactions/")
)


job.commit()