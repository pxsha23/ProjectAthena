"""Where each public benchmark comes from: pinned download URLs, version, licence and citation.

Every value here was checked against the official source on 2026-10-11 (GitHub API, the dataset files
and Crossref for DOIs). GitHub downloads are pinned to a commit, so the files can never change under us.
"""

from dataclasses import dataclass, field

AGIF_COMMIT = "6a4b26bef10abd626ef37f5c2bc16e18ca31762f"
CLINC_COMMIT = "828f8093932c8fe6ca7936c3d2e52903b1c523de"
_AGIF_RAW = f"https://raw.githubusercontent.com/LooperXX/AGIF/{AGIF_COMMIT}/data"
_TICKET_TAGGER = "https://tickettagger.blob.core.windows.net/datasets"

AGIF_CITATION = """@inproceedings{qin-etal-2020-agif,
    title = "{AGIF}: An Adaptive Graph-Interactive Framework for Joint Multiple Intent Detection and Slot Filling",
    author = "Qin, Libo and Xu, Xiao and Che, Wanxiang and Liu, Ting",
    booktitle = "Findings of the Association for Computational Linguistics: EMNLP 2020",
    year = "2020",
    publisher = "Association for Computational Linguistics",
    url = "https://www.aclweb.org/anthology/2020.findings-emnlp.163",
    pages = "1807--1816"
}"""


@dataclass(frozen=True)
class Source:
    name: str
    homepage: str
    version: str
    # Published file name -> download URL. Converters read these files from the raw folder.
    files: dict[str, str]
    licence: str
    citation: str
    notes: tuple[str, ...] = field(default_factory=tuple)


SOURCES: dict[str, Source] = {
    "mixatis": Source(
        name="MixATIS (cleaned)",
        homepage="https://github.com/LooperXX/AGIF",
        version=f"LooperXX/AGIF commit {AGIF_COMMIT}, folder data/MixATIS_clean",
        files={f"{s}.txt": f"{_AGIF_RAW}/MixATIS_clean/{s}.txt" for s in ("train", "dev", "test")},
        licence=(
            "The AGIF repository is licensed GPL-2.0 (GitHub licence field). MixATIS is built from ATIS "
            "(Hemphill et al., 1990), which is distributed by the Linguistic Data Consortium and has no open "
            "licence; use it for research evaluation only and do not redistribute it."
        ),
        citation=AGIF_CITATION,
        notes=(
            "Format: one 'token SLOT-TAG' pair per line, then one line with the intents joined by '#', then a "
            "blank line.",
            "Only the intents are used; slot tags are discarded. The model is compared on intent accuracy only.",
            "Multi-intent utterances have no gold lead intent, so lead is empty.",
        ),
    ),
    "mixsnips": Source(
        name="MixSNIPS (cleaned)",
        homepage="https://github.com/LooperXX/AGIF",
        version=f"LooperXX/AGIF commit {AGIF_COMMIT}, folder data/MixSNIPS_clean",
        files={f"{s}.txt": f"{_AGIF_RAW}/MixSNIPS_clean/{s}.txt" for s in ("train", "dev", "test")},
        licence=(
            "The AGIF repository is licensed GPL-2.0 (GitHub licence field). MixSNIPS is built from the SNIPS "
            "benchmark (https://github.com/sonos/nlu-benchmark), which is licensed CC0-1.0."
        ),
        citation=AGIF_CITATION,
        notes=(
            "Format: one 'token SLOT-TAG' pair per line, then one line with the intents joined by '#', then a "
            "blank line.",
            "Only the intents are used; slot tags are discarded. The model is compared on intent accuracy only.",
            "Multi-intent utterances have no gold lead intent, so lead is empty.",
        ),
    ),
    "clinc150": Source(
        name="CLINC150 (full)",
        homepage="https://github.com/clinc/oos-eval",
        version=f"clinc/oos-eval commit {CLINC_COMMIT}, file data/data_full.json",
        files={
            "data_full.json": f"https://raw.githubusercontent.com/clinc/oos-eval/{CLINC_COMMIT}/data/data_full.json"
        },
        licence="Creative Commons Attribution 3.0 Unported (CC BY 3.0), from the repository's LICENSE file.",
        citation="""@inproceedings{larson-etal-2019-evaluation,
    title = "An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction",
    author = "Larson, Stefan and Mahendran, Anish and Peper, Joseph J. and Clarke, Christopher and Lee, Andrew
      and Hill, Parker and Kummerfeld, Jonathan K. and Leach, Kevin and Laurenzano, Michael A. and
      Tang, Lingjia and Mars, Jason",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing and the
      9th International Joint Conference on Natural Language Processing (EMNLP-IJCNLP)",
    year = "2019",
    url = "https://www.aclweb.org/anthology/D19-1131"
}""",
        notes=(
            "The 'full' version: 150 intents with 100 train, 20 validation and 30 test examples each, plus 100 "
            "train, 100 validation and 1000 test out-of-scope examples.",
            "The official 'val' split is called dev here. Out-of-scope rows (label 'oos') have out_of_scope = "
            "true and an empty label list.",
            "Metrics: in-scope accuracy and out-of-scope recall.",
        ),
    ),
    "nlbse": Source(
        name="NLBSE'22 issue report classification",
        homepage="https://nlbse2022.github.io/tools/",
        version=(
            "Files github-labels-top3-803k-train.tar.gz (248,192,783 bytes) and github-labels-top3-803k-test.tar.gz "
            "(28,614,390 bytes), last modified 2021-11-19, from the competition's Ticket Tagger storage"
        ),
        files={
            "github-labels-top3-803k-train.tar.gz": f"{_TICKET_TAGGER}/github-labels-top3-803k-train.tar.gz",
            "github-labels-top3-803k-test.tar.gz": f"{_TICKET_TAGGER}/github-labels-top3-803k-test.tar.gz",
        },
        licence=(
            "No licence is stated for the data on the competition page or in the files. The issues are public "
            "GitHub issue reports. Cite the competition and do not redistribute the files."
        ),
        citation="""@inproceedings{kallis2022nlbse,
    title = "NLBSE'22 Tool Competition",
    author = "Kallis, Rafael and Chaparro, Oscar and Di Sorbo, Andrea and Panichella, Sebastiano",
    booktitle = "Proceedings of the 1st International Workshop on Natural Language-based Software Engineering",
    year = "2022",
    pages = "25--28",
    doi = "10.1145/3528588.3528664"
}""",
        notes=(
            "Labels: bug, enhancement, question (one per issue). Text is the issue title and body.",
            "Official train and test splits. There is no official dev split: one is cut from train with the "
            "configured seed and fraction, after train is sampled down to the configured cap. Test is complete.",
            "Official metric, quoted from the competition page: 'The submissions will be ranked based on the F1 "
            "score achieved by the proposed classifiers on the test set, as indicated in the papers.' The page "
            "does not say which average; the competition's Colab notebook defines it.",
        ),
    ),
}
