import argparse
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

# Project root:
# recommendation-streaming-platform/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

def load_interactions(data_path):
    """Load all interaction Parquet files from a directory."""

    files = list(Path(data_path).glob("*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"No Parquet files found in {data_path}"
        )
    return pd.concat(
        [pd.read_parquet(file) for file in files],
        ignore_index=True,
    )


def temporal_split(df):
    """
    For each user, reserve their latest interaction
    for testing and use earlier interactions for training.
    """
    df = df.sort_values(
        ["user_id", "last_interaction"]
    ).copy()
    test_indices = (
        df.groupby("user_id")
        .tail(1)
        .index
    )

    test = df.loc[test_indices].copy()
    train = df.drop(test_indices).copy()

    return train, test


def build_matrix(train):
    """
    Create a user x product sparse interaction matrix.
    """

    users = sorted(train["user_id"].unique())
    products = sorted(train["product_id"].unique())

    user_to_index = {
        user: index
        for index, user in enumerate(users)
    }

    product_to_index = {
        product: index
        for index, product in enumerate(products)
    }

    rows = train["user_id"].map(user_to_index)
    cols = train["product_id"].map(product_to_index)

    matrix = csr_matrix(
        (
            train["interaction_score"].astype(float),
            (rows, cols),
        ),
        shape=(len(users), len(products)),
    )

    return (
        matrix,
        users,
        products,
        user_to_index,
        product_to_index,
    )


def train_model(matrix):
    """
    Learn latent user/product factors using TruncatedSVD.
    """

    n_components = min(
        20,
        matrix.shape[0] - 1,
        matrix.shape[1] - 1,
    )

    model = TruncatedSVD(
        n_components=n_components,
        random_state=42,
    )

    user_factors = model.fit_transform(matrix)

    return model, user_factors


def recommend(
    user_id,
    matrix,
    model,
    user_factors,
    users,
    products,
    user_to_index,
    product_to_index,
    seen_products,
    k=10,
):
    """
    Generate personalized recommendations for a user.

    Products already seen by the user during training
    are excluded from the recommendations.
    """

    if user_id not in user_to_index:
        return []

    user_index = user_to_index[user_id]

    # Reconstruct user-product preference scores.
    scores = (
        user_factors[user_index]
        @ model.components_
    )

    scores = scores.copy()

    # Do not recommend products the user already
    # interacted with during training.
    for product in seen_products.get(user_id, set()):

        if product in product_to_index:
            scores[
                product_to_index[product]
            ] = -np.inf

    top_indices = np.argsort(scores)[::-1][:k]

    return [
        {
            "product_id": products[index],
            "score": float(scores[index]),
        }
        for index in top_indices
    ]


def precision_at_k(
    test,
    matrix,
    model,
    user_factors,
    users,
    products,
    user_to_index,
    product_to_index,
    seen_products,
    k=10,
):
    """
    Measure the fraction of recommended items that
    appear in the user's held-out test interaction.

    In this project, each user has exactly one held-out
    interaction, so Precision@10 is hits / (users * 10).
    """

    hits = 0
    evaluated_users = 0

    test_by_user = test.groupby("user_id")

    for user_id, user_test in test_by_user:

        if user_id not in user_to_index:
            continue

        actual_products = set(
            user_test["product_id"]
        )

        recommendations = recommend(
            user_id,
            matrix,
            model,
            user_factors,
            users,
            products,
            user_to_index,
            product_to_index,
            seen_products,
            k,
        )

        recommended_products = {
            item["product_id"]
            for item in recommendations
        }

        hits += len(
            recommended_products
            & actual_products
        )

        evaluated_users += 1

    if evaluated_users == 0:
        return 0.0

    return hits / (evaluated_users * k)


def recall_at_k(
    test,
    matrix,
    model,
    user_factors,
    users,
    products,
    user_to_index,
    product_to_index,
    seen_products,
    k=10,
):
    """
    Measure the fraction of held-out products that
    appear in the user's top-k recommendations.

    Each user has exactly one held-out interaction,
    so this is effectively the percentage of users
    whose held-out product was recommended.
    """

    hits = 0
    relevant = 0

    test_by_user = test.groupby("user_id")

    for user_id, user_test in test_by_user:

        if user_id not in user_to_index:
            continue

        actual_products = set(
            user_test["product_id"]
        )

        recommendations = recommend(
            user_id,
            matrix,
            model,
            user_factors,
            users,
            products,
            user_to_index,
            product_to_index,
            seen_products,
            k,
        )

        recommended_products = {
            item["product_id"]
            for item in recommendations
        }

        hits += len(
            recommended_products
            & actual_products
        )

        relevant += len(actual_products)

    if relevant == 0:
        return 0.0

    return hits / relevant


def popularity_recommendations(
    train,
    k=10,
):
    """
    Recommend the globally most-interacted-with products.

    This is the non-personalized baseline that we use
    to determine whether the SVD model provides useful
    personalization.
    """

    popularity = (
        train.groupby("product_id")["interaction_score"]
        .sum()
        .sort_values(ascending=False)
    )

    return popularity.head(k).index.tolist()


def evaluate_popularity_baseline(
    train,
    test,
    k=10,
):
    """
    Evaluate the global popularity recommender using
    the exact same held-out test set as the SVD model.
    """

    recommendations = set(
        popularity_recommendations(
            train,
            k,
        )
    )

    hits = 0
    evaluated_users = 0

    for user_id, user_test in test.groupby("user_id"):

        actual_products = set(
            user_test["product_id"]
        )

        hits += len(
            recommendations
            & actual_products
        )

        evaluated_users += 1

    if evaluated_users == 0:
        return 0.0, 0.0

    precision = (
        hits
        / (evaluated_users * k)
    )

    total_relevant = sum(
        test.groupby("user_id")["product_id"]
        .nunique()
    )

    if total_relevant == 0:
        recall = 0.0
    else:
        recall = hits / total_relevant

    return precision, recall


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data-path",
        default=str(
            PROJECT_ROOT
            / "data"
            / "interactions"
        ),
    )

    parser.add_argument(
        "--model-dir",
        default=str(
            PROJECT_ROOT
            / "models"
        ),
    )

    args = parser.parse_args()

    # -----------------------------------------------------
    # Load data
    # -----------------------------------------------------

    print("Loading interaction data...")

    df = load_interactions(
        args.data_path
    )

    print(
        f"Interactions: {len(df):,}"
    )

    print(
        f"Users: {df.user_id.nunique():,}"
    )

    print(
        f"Products: {df.product_id.nunique():,}"
    )

    # -----------------------------------------------------
    # Train/test split
    # -----------------------------------------------------

    print(
        "\nCreating temporal train/test split..."
    )

    train, test = temporal_split(df)

    print(
        f"Training interactions: "
        f"{len(train):,}"
    )

    print(
        f"Test interactions: "
        f"{len(test):,}"
    )

    # -----------------------------------------------------
    # Build interaction matrix
    # -----------------------------------------------------

    print(
        "\nBuilding user × product matrix..."
    )

    (
        matrix,
        users,
        products,
        user_to_index,
        product_to_index,
    ) = build_matrix(train)

    print(
        f"Matrix shape: "
        f"{matrix.shape[0]:,} users × "
        f"{matrix.shape[1]:,} products"
    )

    # -----------------------------------------------------
    # Train SVD model
    # -----------------------------------------------------

    print(
        "\nTraining recommendation model..."
    )

    model, user_factors = train_model(
        matrix
    )

    print(
        f"Latent dimensions: "
        f"{model.n_components}"
    )

    # -----------------------------------------------------
    # Identify products already seen
    # -----------------------------------------------------

    seen_products = (
        train
        .groupby("user_id")["product_id"]
        .apply(set)
        .to_dict()
    )

    # -----------------------------------------------------
    # Evaluate SVD model
    # -----------------------------------------------------

    print(
        "\nEvaluating SVD model..."
    )

    precision = precision_at_k(
        test,
        matrix,
        model,
        user_factors,
        users,
        products,
        user_to_index,
        product_to_index,
        seen_products,
        k=10,
    )

    recall = recall_at_k(
        test,
        matrix,
        model,
        user_factors,
        users,
        products,
        user_to_index,
        product_to_index,
        seen_products,
        k=10,
    )

    print(
        f"\nSVD Precision@10: "
        f"{precision:.4f}"
    )

    print(
        f"SVD Recall@10:    "
        f"{recall:.4f}"
    )

    # -----------------------------------------------------
    # Evaluate popularity baseline
    # -----------------------------------------------------

    print(
        "\nEvaluating popularity baseline..."
    )

    baseline_precision, baseline_recall = (
        evaluate_popularity_baseline(
            train,
            test,
            k=10,
        )
    )

    print(
        f"\nPopularity Precision@10: "
        f"{baseline_precision:.4f}"
    )

    print(
        f"Popularity Recall@10:    "
        f"{baseline_recall:.4f}"
    )

    # -----------------------------------------------------
    # Compare model vs baseline
    # -----------------------------------------------------

    print(
        "\nModel vs. baseline:"
    )

    precision_difference = (
        precision
        - baseline_precision
    )

    recall_difference = (
        recall
        - baseline_recall
    )

    print(
        f"Precision improvement: "
        f"{precision_difference:+.4f}"
    )

    print(
        f"Recall improvement:    "
        f"{recall_difference:+.4f}"
    )

    # -----------------------------------------------------
    # Show example recommendations
    # -----------------------------------------------------

    example_user = users[0]

    recommendations = recommend(
        example_user,
        matrix,
        model,
        user_factors,
        users,
        products,
        user_to_index,
        product_to_index,
        seen_products,
        k=10,
    )

    print(
        f"\nTop recommendations for "
        f"{example_user}:"
    )

    for rank, recommendation in enumerate(
        recommendations,
        start=1,
    ):
        print(
            f"{rank:2d}. "
            f"{recommendation['product_id']} "
            f"(score="
            f"{recommendation['score']:.4f})"
        )

    # -----------------------------------------------------
    # Save inference-ready model artifact
    # -----------------------------------------------------

    model_dir = Path(
        args.model_dir
    )

    model_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact = {
        # Store only the numerical components required
        # for inference. The sklearn TruncatedSVD object
        # itself is intentionally not serialized.
        "components": model.components_,
        "users": users,
        "products": products,
        "user_to_index": user_to_index,
        "product_to_index": product_to_index,
        "user_factors": user_factors,
        "seen_products": seen_products,
    }

    output_path = (
        model_dir
        / "recommender.joblib"
    )

    joblib.dump(
        artifact,
        output_path,
    )

    print(
        f"\nModel saved to: "
        f"{output_path}"
    )


if __name__ == "__main__":
    main()