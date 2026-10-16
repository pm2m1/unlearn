"""Print topic and subtopic sizes for Number and Algebra, to choose the demo topic slice."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SUBJECTS = ["Number", "Algebra"]


def summarise(misc: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    return (
        misc.groupby(by)
        .agg(constructs=("ConstructId", "nunique"), misconceptions=("MisconceptionId", "nunique"))
        .sort_values("constructs", ascending=False)
    )


def main():
    constructs = pd.read_csv(RAW / "construct-map.csv")
    misc = pd.read_csv(RAW / "misconception-map.csv")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 500)
    pd.set_option("display.max_colwidth", 60)

    for subject in SUBJECTS:
        c = constructs[constructs.SubjectName == subject]
        m = misc[misc.SubjectName == subject]
        print(f"\n=== {subject}: {c.TopicName.nunique()} topics, {c.SubTopicName.nunique()} subtopics, "
              f"{c.ConstructId.nunique()} constructs, {m.MisconceptionId.nunique()} misconceptions")

        topics = summarise(m, ["TopicName"])
        topics.insert(0, "subtopics", c.groupby("TopicName").SubTopicName.nunique())
        print(topics.to_string())

        for topic in topics.index:
            print(f"\n  -- {topic}")
            print(summarise(m[m.TopicName == topic], ["SubTopicName"]).to_string().replace("\n", "\n  "))


if __name__ == "__main__":
    main()
