# Real-data eval: the data

## Source

**Eedi, Diagnostic Questions: The NeurIPS 2020 Education Challenge** (Wang et al., 2020, [arXiv:2007.12061](https://arxiv.org/abs/2007.12061)).

- Project page: https://eedi.com/projects/neurips-education-challenge
- Download (public, no form): https://dqanonymousdata.blob.core.windows.net/neurips-public/data.zip
- Size 656,787,242 bytes, MD5 `68ac2703d65bc350cca37653917adacb` (base64 `aKwnA9Zbw1DMo3ZTkXrayw==`, matching the server's `Content-MD5`), last modified 2020-11-19. Downloaded 2026-10-18.

## Licence

**CC BY-NC-ND 4.0**: stated on the project page above, read by Parth on 2026-10-18; the page later returned 404. The zip itself carries no licence file. The challenge guide adds that the question images were shared for the competition only.

What that means here:

- **Nothing from the dataset is committed.** It lives in `data/external/` (git-ignored): the raw files, and anything per student or per answer derived from them (splits, predictions, fitted per-student state).
- **Committed:** code, our own mapping file (`subtopic_edges.csv`, built from our curated edges and the Eedi Misconceptions Graph, CC BY 4.0), and aggregate results (metrics over thousands of students, with no per-student rows).
- **The images are never extracted or used.** Only the CSVs are unzipped; the 1,898 files under `images/` stay inside the zip.

## Setup

```
mkdir -p data/external && cd data/external
curl -o neurips2020.zip https://dqanonymousdata.blob.core.windows.net/neurips-public/data.zip
md5 -q neurips2020.zip          # 68ac2703d65bc350cca37653917adacb  (md5sum on Linux)
unzip -q neurips2020.zip 'data/metadata/*' 'data/train_data/*.csv' 'data/test_data/*.csv' -d neurips2020
```

## Files used (Tasks 1 and 2 dataset)

| File | Rows | Used for |
| --- | --- | --- |
| `train_data/train_task_1_2.csv` | 15,867,850 | answers: QuestionId, UserId, AnswerId, IsCorrect, CorrectAnswer, AnswerValue |
| `test_data/test_{public,private}_answers_task_1.csv` | 3,966,963 | more answers by the same students (IsCorrect) |
| `test_data/test_{public,private}_answers_task_2.csv` | 3,966,963 | the same answers' AnswerValue, joined on AnswerId |
| `metadata/answer_metadata_task_1_2.csv` | 19,834,820 | DateAnswered (minute resolution), QuizId |
| `metadata/question_metadata_task_1_2.csv` | 27,613 | each question's SubjectId path |
| `metadata/subject_metadata.csv` | 388 | the subject tree (Level 0–3) |

The challenge's train/test split is ignored: train and test answers are pooled into one history per student, and this eval makes its own split, by student (see `PREREGISTRATION.md`).

## Link to our graph

NeurIPS SubjectIds are Eedi's own subject IDs, the same ones the Eedi Misconceptions Graph uses: 259 of the graph's 290 Subject/Topic/SubTopic IDs appear in `subject_metadata.csv`, 245 with identical names and 14 with spelling-only differences ("Coordinates" / "Co-ordinates"). The finest level in NeurIPS is SubTopic (Level 3), with no construct level and no question text, so questions map exactly to SubTopics but not to our constructs. The eval therefore runs on our 40 constructs' 7 SubTopics, with the curated `REQUIRES` edges collapsed onto them (`build_subtopic_edges.py`, `subtopic_edges.csv`).

Subset: questions with a Level-3 SubjectId in {204, 219, 220, 226, 227, 228, 230}; students with 10 or more such answers: 51,211 students, 1,664,359 answers.
