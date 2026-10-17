"""DRAFT question bank for the Fractions slice. Writes data/curated/questions.json.

Every wrong option names the misconception a student would need to hold to pick it, with a
`why` showing the working. Options flagged `stretch` are weaker fits for review. The script
verifies every question (maths via fractions.Fraction, SEEN_IN via the Eedi CSV) and refuses
to write the file if any fail.
"""

import json
import random
import sys
from pathlib import Path

import pandas as pd

from unlearn.curation import CURATED, verify_question

ROOT = Path(__file__).resolve().parents[1]


def D(text, mid, why, stretch=False, claim=None):
    d = {"text": text, "misconception_id": mid, "why": why}
    if stretch:
        d["stretch"] = True
    if claim:
        d["claim"] = claim
    return d


def C(text, claim=None):
    d = {"text": text, "correct": True}
    if claim:
        d["claim"] = claim
    return d


def val(expr, **kw):
    return {"kind": "value", "expr": expr, **kw}


# (construct_id, text, check, correct option, [distractors])
BANK = [
    # --- 3342 Read fractions --------------------------------------------------
    (3342, "Which of these shows four sevenths?", val("F(4,7)", words=True), C("4/7"), [
        D("7/4", 14092, "Swaps numerator and denominator."),
        D("47", 14014, "Writes the two numbers as one integer instead of a fraction."),
        D("4.7", 15450, "Thinks a/b is written a.b, so four sevenths is 4.7."),
    ]),
    (3342, "Which fraction has a numerator of 2 and a denominator of 9?", val("F(2,9)"), C("2/9"), [
        D("9/2", 16784, "Thinks the denominator goes on top."),
        D("29", 14014, "Writes the numbers side by side as an integer."),
        D("2 1/9", 14121, "Uses the numerator as a whole-number part.", stretch=True),
    ]),
    (3342, "Which mixed number is equal to 7/3?", val("F(7,3)"), C("2 1/3"), [
        D("7 1/3", 21826, "Believes a/b equals the mixed number a 1/b."),
        D("3/7", 14092, "Swaps numerator and denominator."),
        D("7.3", 15450, "Thinks 7/3 is written 7.3."),
    ]),
    # --- 408 Equivalent fractions as shapes ----------------------------------
    (408, "Square A is split into 4 equal parts and 1 part is shaded. Square B is the same size, split into 8 equal parts, and 2 parts are shaded. Which is true?",
     {"kind": "claim", "a": "F(1,4)", "b": "F(2,8)"}, C("A and B show the same fraction", "="), [
        D("B shows more, because it has more shaded parts", 14944, "Compares the count of shaded parts, 2 > 1.", claim="<"),
        D("A shows more, because its parts are bigger", 18649, "Thinks larger sections mean a larger fraction.", claim=">"),
        D("You can't tell without measuring the squares", 18650, "Thinks dimensions are needed to compare fractions.", claim="?"),
    ]),
    (408, "Bar A is split into 5 equal parts with 2 shaded. Bar B is the same size, split into 10 equal parts with 2 shaded. Which is true?",
     {"kind": "claim", "a": "F(2,5)", "b": "F(2,10)"}, C("A has more of its bar shaded than B", ">"), [
        D("They show the same amount, because both have 2 shaded parts", 19079, "Uses the number of shaded parts and ignores the total.", claim="="),
        D("They are equivalent, because 2/5 and 2/10 have the same numerator", 21176, "Believes equal numerators mean equal fractions.", claim="="),
        D("You can't tell without measuring the bars", 18650, "Thinks dimensions are needed to compare fractions.", claim="?"),
    ]),
    (408, "A rectangle is split into 12 equal squares. How many squares must be shaded to show 3/4 of the rectangle?", val("F(3,4)*12"), C("9"), [
        D("4", 19778, "Thinks the denominator says how many sections to shade."),
        D("3", 19079, "Matches the number of shaded parts to the numerator, ignoring the total."),
        D("8", 19773, "Thinks the denominator is the number left unshaded, so leaves 4 and shades 8."),
    ]),
    # --- 409 Equivalent fractions as numbers ---------------------------------
    (409, "Which fraction is equivalent to 2/3?", val("F(2,3)"), C("8/12"), [
        D("3/2", 22644, "Thinks a/b is equivalent to b/a."),
        D("4/3", 22626, "Doubles only the numerator."),
        D("1/2", 20776, "Subtracts 1 from numerator and denominator."),
    ]),
    (409, "Which pair of fractions are equivalent?", {"kind": "pair", "words": True}, C("1/3 and 2/6"), [
        D("1/3 and 1/6", 19786, "Believes all unit fractions are equivalent."),
        D("3/5 and 5/7", 23144, "Adds 2 to numerator and denominator."),
        D("2/5 and 2/9", 17669, "Thinks fractions with the same numerator are equivalent."),
    ]),
    (409, "Find the missing number: 3/4 = ?/20", val("F(3,4)*20"), C("15"), [
        D("19", 14007, "Adds 16 to both parts (4 + 16 = 20, so 3 + 16)."),
        D("3", 22639, "Changes only the denominator."),
        D("5", 19414, "Thinks the multiplier (x5) is the new numerator."),
    ]),
    # --- 410 Simplify to a unit fraction -------------------------------------
    (410, "Simplify 4/12 fully.", {"kind": "simplest", "expr": "F(4,12)"}, C("1/3"), [
        D("2/6", 14537, "Divides by 2 once and stops."),
        D("1/4", 15522, "Divides the numerator by 4 but the denominator by 3."),
        D("4/12", 15267, "Does not see that 4/12 can be simplified."),
    ]),
    (410, "Simplify 6/24 fully.", {"kind": "simplest", "expr": "F(6,24)"}, C("1/4"), [
        D("3/12", 14537, "Divides by 2 once and stops."),
        D("0.6/2.4", 14110, "Divides by 10, leaving decimals in the fraction."),
        D("1/6", 15522, "Divides the numerator by 6 but the denominator by 4."),
    ]),
    (410, "Simplify 2 4/8 fully.", {"kind": "simplest", "expr": "2+F(4,8)"}, C("2 1/2"), [
        D("1 1/2", 14494, "Halves the whole number as well as the fraction."),
        D("2 4/8", 15074, "Believes mixed numbers cannot be simplified."),
        D("2 2/4", 14537, "Divides by 2 once and stops."),
    ]),
    # --- 411 Simplify to a non-unit fraction ---------------------------------
    (411, "Simplify 15/21 fully.", {"kind": "simplest", "expr": "F(15,21)"}, C("5/7"), [
        D("15/21", 14539, "Thinks fractions with an odd numerator and denominator can't be simplified."),
        D("5/2", 14538, "Cancels the digit 1 that appears in both 15 and 21."),
        D("3/7", 15522, "Divides the numerator by 5 but the denominator by 3."),
    ]),
    (411, "Simplify 12/18 fully.", {"kind": "simplest", "expr": "F(12,18)"}, C("2/3"), [
        D("6/9", 14537, "Divides by 2 once and stops."),
        D("4/9", 15522, "Divides the numerator by 3 but the denominator by 2."),
        D("10/16", 24732, "Subtracts 2 from both numerator and denominator."),
    ]),
    (411, "Simplify 14/35 fully.", {"kind": "simplest", "expr": "F(14,35)"}, C("2/5"), [
        D("1.4/3.5", 14110, "Divides by 10, leaving decimals in the fraction."),
        D("14/35", 15267, "Does not see that 14/35 can be simplified."),
    ]),
    # --- 413 Order fractions with the same denominator -----------------------
    (413, "Put these fractions in order from smallest to largest: 5/9, 7/9, 2/9",
     {"kind": "order", "items": ["5/9", "7/9", "2/9"], "dir": "asc"}, C("2/9, 5/9, 7/9"), [
        D("7/9, 5/9, 2/9", 18656, "Believes a larger numerator means a smaller fraction when denominators match."),
        D("5/9, 7/9, 2/9", 18235, "Assumes the last number in the list is the largest and keeps the order."),
        D("5/9, 2/9, 7/9", 18234, "Assumes the first number in the list is the smallest.", stretch=True),
    ]),
    (413, "Which fraction is the largest: 3/11, 8/11, 5/11?", val("max(F(3,11),F(8,11),F(5,11))"), C("8/11"), [
        D("3/11", 18657, "Believes a smaller numerator means a larger fraction when denominators match."),
        D("5/11", 18235, "Assumes the last number in the list is the largest."),
    ]),
    (413, "Which of these is the smallest: 4/7, 1 1/7, 6/7, 2/7?", val("min(F(4,7),1+F(1,7),F(6,7),F(2,7))"), C("2/7"), [
        D("1 1/7", 18659, "Treats the whole number and fraction in 1 1/7 separately and sees 1/7."),
        D("6/7", 14068, "Mixes up smallest and largest."),
        D("4/7", 18234, "Assumes the first number in the list is the smallest."),
    ]),
    # --- 417 Inequality notation, same denominator ----------------------------
    (417, "Compare 5/8 and 3/8. Which statement is true?", {"kind": "statement", "words": True}, C("5/8 > 3/8"), [
        D("5/8 < 3/8", 18657, "Believes a smaller numerator means a larger fraction."),
        D("5/8 = 3/8", 14089, "Believes fractions with the same denominator are equal."),
    ]),
    (417, "Which symbol makes this true? 2/9 ? 7/9", {"kind": "symbol", "a": "F(2,9)", "b": "F(7,9)"}, C("<"), [
        D(">", 15852, "Thinks the greater than symbol means less than."),
        D("=", 14089, "Believes fractions with the same denominator are equal."),
        D("+", 23849, "Believes a missing symbol must be an operation."),
    ]),
    (417, "Which symbol makes this true? 9/10 ? 7/10", {"kind": "symbol", "a": "F(9,10)", "b": "F(7,10)"}, C(">"), [
        D("<", 18657, "Believes a smaller numerator means a larger fraction."),
        D("=", 15582, "Compares only the denominators, which are the same."),
        D("-", 23849, "Believes a missing symbol must be an operation."),
    ]),
    # --- 3320 Inequality notation, same numerator ----------------------------
    (3320, "Which symbol makes this true? 3/5 ? 3/8", {"kind": "symbol", "a": "F(3,5)", "b": "F(3,8)"}, C(">"), [
        D("<", 14090, "Believes fractions with larger denominators are larger."),
        D("=", 15439, "Believes equal numerators mean equal fractions."),
    ]),
    (3320, "Compare 2/7 and 2/3. Which statement is true?", {"kind": "statement", "words": True}, C("2/7 < 2/3"), [
        D("2/7 > 2/3", 14090, "Believes fractions with larger denominators are larger."),
        D("2/7 = 2/3", 17372, "Compares only the numerators, which are the same."),
    ]),
    (3320, "Which is true about 4/9 and 4/5?", {"kind": "claim", "a": "F(4,9)", "b": "F(4,5)"}, C("4/9 is smaller than 4/5", "<"), [
        D("4/9 is bigger, because 9 is bigger than 5", 14090, "Believes fractions with larger denominators are larger.", claim=">"),
        D("They are equal, because the numerators are the same", 15439, "Believes equal numerators mean equal fractions.", claim="="),
    ]),
    # --- 418 Inequality notation, denominators are multiples ------------------
    (418, "Which symbol makes this true? 2/3 ? 5/6", {"kind": "symbol", "a": "F(2,3)", "b": "F(5,6)"}, C("<"), [
        D("=", 17374, "Both are 1 part away from a whole, so thinks they are equally close to 1."),
        D(">", 15438, "Believes the fraction with the largest denominator is smallest."),
    ]),
    (418, "Compare 3/4 and 7/12. Which statement is true?", {"kind": "statement", "words": True}, C("3/4 > 7/12"), [
        D("3/4 < 7/12", 17372, "Compares only the numerators, 3 < 7."),
        D("7/12 > 3/4", 14090, "Believes fractions with larger denominators are larger."),
    ]),
    (418, "Which is the largest: 2/3, 7/12, 5/6?", val("max(F(2,3),F(7,12),F(5,6))"), C("5/6"), [
        D("7/12", 17372, "Picks the largest numerator."),
        D("2/3", 15438, "Ranks by denominator, so the smallest denominator is largest.", stretch=True),
    ]),
    # --- 419 Inequality notation, unrelated denominators ---------------------
    (419, "Which symbol makes this true? 2/3 ? 3/5", {"kind": "symbol", "a": "F(2,3)", "b": "F(3,5)"}, C(">"), [
        D("<", 18663, "Believes a larger numerator means a larger fraction."),
        D("+", 23849, "Believes a missing symbol must be an operation."),
    ]),
    (419, "Compare 3/4 and 4/5. Which statement is true?", {"kind": "statement", "words": True}, C("3/4 < 4/5"), [
        D("3/4 > 4/5", 15438, "Believes the fraction with the largest denominator is smallest."),
        D("4/5 < 3/4", 22129, "Confuses the greater than and less than symbols."),
    ]),
    (419, "Which is the largest: 5/6, 7/9, 3/4?", val("max(F(5,6),F(7,9),F(3,4))"), C("5/6"), [
        D("7/9", 18663, "Believes a larger numerator means a larger fraction."),
        D("3/4", 15438, "Ranks by denominator, so the smallest denominator is largest."),
    ]),
    # --- 414 Order fractions, denominators are multiples ---------------------
    (414, "Put these fractions in order from smallest to largest: 1/2, 3/8, 3/4",
     {"kind": "order", "items": ["1/2", "3/8", "3/4"], "dir": "asc"}, C("3/8, 1/2, 3/4"), [
        D("1/2, 3/4, 3/8", 18664, "Believes a larger denominator means a larger fraction."),
        D("3/8, 3/4, 1/2", 18665, "Believes a larger denominator means a smaller fraction."),
        D("1/2, 3/8, 3/4", 19024, "Copies the order from the question."),
    ]),
    (414, "Which is the largest: 5/6, 2/3, 7/12, 11/12?", val("max(F(5,6),F(2,3),F(7,12),F(11,12))"), C("11/12"), [
        D("2/3", 18661, "Believes the fraction with the smallest denominator is largest."),
        D("7/12", 14068, "Mixes up smallest and largest."),
    ]),
    (414, "Put these fractions in order from smallest to largest: 1/6, 1/3, 1/12",
     {"kind": "order", "items": ["1/6", "1/3", "1/12"], "dir": "asc"}, C("1/12, 1/6, 1/3"), [
        D("1/3, 1/6, 1/12", 14081, "Believes unit fractions with larger denominators are larger."),
        D("1/6, 1/3, 1/12", 19024, "Copies the order from the question."),
        D("1/6, 1/12, 1/3", 18234, "Assumes the first number in the list is the smallest.", stretch=True),
    ]),
    # --- 415 Order fractions, unrelated denominators -------------------------
    (415, "Put these fractions in order from smallest to largest: 3/5, 1/2, 2/3",
     {"kind": "order", "items": ["3/5", "1/2", "2/3"], "dir": "asc"}, C("1/2, 3/5, 2/3"), [
        D("1/2, 2/3, 3/5", 19420, "Orders by numerator: smaller numerator means smaller fraction."),
        D("3/5, 2/3, 1/2", 22647, "Believes a smaller denominator means a larger fraction."),
        D("3/5, 1/2, 2/3", 15482, "Assumes the list is already in size order."),
    ]),
    (415, "Which is the smallest: 2/3, 3/5, 5/8?", val("min(F(2,3),F(3,5),F(5,8))"), C("3/5"), [
        D("2/3", 19420, "Picks the smallest numerator."),
        D("5/8", 18665, "Believes a larger denominator means a smaller fraction."),
    ]),
    (415, "Put these fractions in order from largest to smallest: 2/5, 1/3, 3/7",
     {"kind": "order", "items": ["2/5", "1/3", "3/7"], "dir": "desc"}, C("3/7, 2/5, 1/3"), [
        D("1/3, 2/5, 3/7", 14068, "Mixes up largest and smallest, giving the ascending order."),
        D("2/5, 1/3, 3/7", 19024, "Copies the order from the question."),
    ]),
    # --- 3632 Estimate with benchmark fractions ------------------------------
    (3632, "Estimate 7/8 - 1/9 by rounding each fraction to 0, 1/2 or 1.", val("1-0"), C("1"), [
        D("6/17", 15931, "Subtracts the numerators and adds the denominators."),
        D("55/72", 22411, "Works out the exact answer instead of estimating."),
        D("1/2", 22351, "Rounds every fraction up, so 1/9 becomes 1/2."),
    ]),
    (3632, "Estimate 5/9 + 11/12 by rounding each fraction to 0, 1/2 or 1.", val("F(1,2)+1"), C("1 1/2"), [
        D("1", 22168, "Rounds every fraction down, so 11/12 becomes 1/2."),
        D("2", 22351, "Rounds every fraction up, so 5/9 becomes 1."),
        D("1 17/36", 22411, "Works out the exact answer instead of estimating."),
    ]),
    (3632, "Estimate 4/7 - 1/12 by rounding each fraction to 0, 1/2 or 1.", val("F(1,2)-0"), C("1/2"), [
        D("3/19", 15931, "Subtracts the numerators and adds the denominators."),
        D("41/84", 22411, "Works out the exact answer instead of estimating."),
    ]),
    # --- 3839 Two whole numbers a fraction lies between ----------------------
    (3839, "Which two whole numbers does 17/5 lie between?", {"kind": "between", "expr": "F(17,5)"}, C("3 and 4"), [
        D("0 and 1", 16966, "Does not see that an improper fraction is greater than 1."),
    ]),
    (3839, "Which two whole numbers does 11/4 lie between?", {"kind": "between", "expr": "F(11,4)"}, C("2 and 3"), [
        D("0 and 1", 16966, "Does not see that an improper fraction is greater than 1."),
    ]),
    (3839, "Which two whole numbers does 23/6 lie between?", {"kind": "between", "expr": "F(23,6)"}, C("3 and 4"), [
        D("0 and 1", 16966, "Does not see that an improper fraction is greater than 1."),
    ]),
    # --- 3118 Read a fraction on a scale --------------------------------------
    (3118, "A number line goes from 0 to 1. It is split into 5 equal gaps by 4 dashes. An arrow points to the 3rd dash after 0. What number is at the arrow?",
     val("F(3,5)"), C("3/5"), [
        D("3/4", 15999, "Counts the 4 dashes as the divisions, one too few."),
        D("3/10", 18121, "Assumes every dash is worth 0.1."),
        D("1/2", 18155, "Assumes the arrow is halfway between the labels."),
    ]),
    (3118, "A number line goes from 2 to 3. It is split into 4 equal gaps by 3 dashes. An arrow points to the 1st dash after 2. What number is at the arrow?",
     val("2+F(1,4)"), C("2 1/4"), [
        D("1/4", 15046, "Forgets to add on the starting value of 2."),
        D("3", 18486, "Treats each dash as worth 1."),
        D("2 1/3", 15999, "Counts the 3 dashes as the divisions, one too few."),
    ]),
    (3118, "A number line goes from 0 to 2. It is split into 8 equal gaps by 7 dashes. An arrow points to the 3rd dash after 0. What number is at the arrow?",
     val("F(3,8)*2"), C("3/4"), [
        D("3/8", 15358, "Assumes a fraction scale only goes from 0 to 1."),
        D("3", 18486, "Treats each dash as worth 1."),
        D("3/7", 15999, "Counts the 7 dashes as the divisions, one too few."),
    ]),
    # --- 421 Non-unit fractions on a number line -----------------------------
    (421, "A number line from 0 to 1 is split into 6 equal gaps. An arrow points to the 4th dash after 0. Which fraction is at the arrow?",
     val("F(4,6)"), C("4/6"), [
        D("1/4", 18805, "Assumes a unit fraction with the dash count (4) as the denominator."),
        D("6/4", 18297, "Believes x/y is the same as y/x."),
        D("4/7", 15304, "Counts the 7 marks (lines) instead of the 6 gaps."),
    ]),
    (421, "A number line from 0 to 2 is split into 10 equal gaps. An arrow points to the 3rd dash after 0. Which number is at the arrow?",
     val("F(3,10)*2"), C("3/5"), [
        D("3/10", 18806, "Assumes the whole line is 1."),
        D("3", 15112, "Assumes every dash is worth 1."),
        D("1/3", 18805, "Assumes a unit fraction with the dash count (3) as the denominator."),
    ]),
    (421, "A number line from 0 to 1 is split into 10 equal gaps. An arrow points to the 7th dash after 0. Which fraction is at the arrow?",
     val("F(7,10)"), C("7/10"), [
        D("1/7", 18805, "Assumes a unit fraction with the dash count (7) as the denominator."),
        D("10/7", 18297, "Believes x/y is the same as y/x."),
        D("7/11", 15304, "Counts the 11 marks (lines) instead of the 10 gaps."),
    ]),
    # --- 420 Unit fractions on a number line ---------------------------------
    (420, "A number line from 0 to 1 is split into 5 equal gaps. What fraction is at the first dash after 0?", val("F(1,5)"), C("1/5"), [
        D("1", 18349, "Believes the first mark on a number line is always 1."),
        D("1/6", 15304, "Counts the 6 marks (lines) instead of the 5 gaps."),
        D("0.5", 26288, "Writes the denominator after the decimal point: 1/5 = 0.5."),
    ]),
    (420, "To mark 1/3 on a number line from 0 to 1, how many equal gaps should the line be split into?", val("3"), C("3"), [
        D("4", 15304, "Counts marks instead of gaps: 4 marks make 3 gaps."),
        D("2", 18904, "Does not split the line into the right number of parts.", stretch=True),
    ]),
    (420, "A number line from 0 to 1 is split into 8 equal gaps. What fraction is at the first dash after 0?", val("F(1,8)"), C("1/8"), [
        D("1", 18349, "Believes the first mark on a number line is always 1."),
        D("1/9", 15304, "Counts the 9 marks (lines) instead of the 8 gaps."),
        D("0.8", 26288, "Writes the denominator after the decimal point: 1/8 = 0.8."),
    ]),
    # --- 3587 Fractions only compare with the same whole ---------------------
    (3587, "Ana eats 1/2 of a small pizza. Ben eats 1/2 of a large pizza that is twice the size of the small one. Who ate more pizza?",
     {"kind": "claim", "a": "F(1,2)*1", "b": "F(1,2)*2"}, C("Ben ate more", "<"), [
        D("They ate the same amount, because both ate 1/2", 16804, "Believes the same fraction of different wholes is the same amount.", claim="="),
    ]),
    (3587, "Sam drinks 1/4 of a 1 litre bottle. Mia drinks 1/4 of a 2 litre bottle. Who drank more?",
     {"kind": "claim", "a": "F(1,4)*1", "b": "F(1,4)*2"}, C("Mia drank more", "<"), [
        D("They drank the same amount, because both drank 1/4", 16804, "Believes the same fraction of different wholes is the same amount.", claim="="),
    ]),
    (3587, "Leo reads 1/3 of a 90-page book. Zoe reads 1/3 of a 60-page book. Who read more pages?",
     {"kind": "claim", "a": "F(1,3)*90", "b": "F(1,3)*60"}, C("Leo read more pages", ">"), [
        D("They read the same number of pages, because both read 1/3", 16804, "Believes the same fraction of different wholes is the same amount.", claim="="),
    ]),
    # --- 424 Add proper fractions, same denominator --------------------------
    (424, "2/7 + 3/7 = ?", val("F(2,7)+F(3,7)"), C("5/7"), [
        D("5/14", 21651, "Adds numerators and adds denominators."),
        D("6/7", 21177, "Multiplies the numerators."),
        D("5", 19219, "Adds the numerators and thinks the denominators cancel."),
    ]),
    (424, "2/9 + 2/9 = ?", val("F(2,9)+F(2,9)"), C("4/9"), [
        D("2/18", 19192, "With the same numerators, adds the denominators and keeps the numerator."),
        D("4/18", 21651, "Adds numerators and adds denominators."),
        D("4/81", 15031, "Multiplies instead of adding."),
    ]),
    (424, "1/5 + 3/5 = ?", val("F(1,5)+F(3,5)"), C("4/5"), [
        D("3/10", 18355, "Adds the denominators and multiplies the numerators."),
        D("4/6", 19251, "Adds the 1 from 1/5 to both parts of 3/5."),
        D("3/5", 15032, "Multiplies the numerators: 1 x 3 = 3."),
    ]),
    # --- 430 Add improper fractions, same denominator ------------------------
    (430, "A recipe uses 7/4 cups of flour, then 5/4 cups more. How much flour is used altogether?", val("F(7,4)+F(5,4)"), C("3"), [
        D("2/4", 18310, "Finds the difference between the amounts instead of the total."),
        D("12/8", 21651, "Adds numerators and adds denominators."),
    ]),
    (430, "Tom runs 9/5 km on Monday and 8/5 km on Tuesday. How far does he run in total?", val("F(9,5)+F(8,5)"), C("17/5"), [
        D("1/5", 18310, "Finds the difference between the distances instead of the total."),
        D("17/10", 21651, "Adds numerators and adds denominators."),
    ]),
    (430, "One jug holds 5/3 litres and another holds 7/3 litres. How much do they hold altogether?", val("F(5,3)+F(7,3)"), C("4"), [
        D("2/3", 18310, "Finds the difference between the amounts instead of the total."),
        D("12/6", 21651, "Adds numerators and adds denominators."),
    ]),
    # --- 428 Add mixed numbers, same denominator -----------------------------
    (428, "1 2/5 + 2 1/5 = ?", val("1+F(2,5)+2+F(1,5)"), C("3 3/5"), [
        D("3", 18151, "Adds only the whole numbers."),
        D("2 2/25", 26058, "Multiplies the wholes (1 x 2) and multiplies the fractions."),
        D("3 3/10", 21651, "Adds numerators and adds denominators in the fraction part."),
    ]),
    (428, "1 3/8 + 2/8 = ?", val("1+F(3,8)+F(2,8)"), C("1 5/8"), [
        D("6/8", 15333, "Adds the whole number to the numerators: 1 + 3 + 2 = 6."),
        D("1 6/64", 18227, "Multiplies the fraction parts instead of adding them."),
        D("1 5/16", 21651, "Adds numerators and adds denominators in the fraction part."),
    ]),
    (428, "2 3/4 + 1 3/4 = ?", val("2+F(3,4)+1+F(3,4)"), C("4 1/2"), [
        D("3", 18151, "Adds only the whole numbers."),
        D("2 9/16", 26058, "Multiplies the wholes (2 x 1) and multiplies the fractions."),
        D("3 6/8", 21651, "Adds numerators and adds denominators in the fraction part."),
    ]),
    # --- 429 Add mixed numbers, different denominators -----------------------
    (429, "1 1/2 + 2 1/3 = ?", val("1+F(1,2)+2+F(1,3)"), C("3 5/6"), [
        D("3 2/5", 19849, "Adds numerators and adds denominators."),
        D("3 2/6", 22639, "Changes the denominators to 6 but not the numerators."),
        D("3 1/6", 15472, "Multiplies numerators and denominators to get a common denominator."),
    ]),
    (429, "2 3/4 + 1 1/2 = ?", val("2+F(3,4)+1+F(1,2)"), C("4 1/4"), [
        D("3 1/4", 26998, "Gets 5/4 but drops the extra whole, keeping 3 wholes."),
        D("3 4/6", 19849, "Adds numerators and adds denominators."),
        D("3 4/4", 22639, "Changes 1/2 to quarters without changing its numerator: 3/4 + 1/4."),
    ]),
    (429, "1 2/3 + 1 1/6 = ?", val("1+F(2,3)+1+F(1,6)"), C("2 5/6"), [
        D("2 3/9", 19849, "Adds numerators and adds denominators."),
        D("2 3/6", 22639, "Changes 2/3 to sixths without changing its numerator."),
        D("2 5/12", 26999, "Converts to 4/6 + 1/6, then adds the denominators too."),
    ]),
    # --- 425 Add, one denominator a multiple of the other --------------------
    (425, "1/2 + 1/4 = ?", val("F(1,2)+F(1,4)"), C("3/4"), [
        D("1/6", 14220, "With identical numerators, keeps the numerator and adds the denominators."),
        D("2/4", 26989, "Changes 1/2 to quarters but keeps the numerator 1."),
        D("1/8", 15031, "Multiplies instead of adding."),
    ]),
    (425, "2/3 + 1/6 = ?", val("F(2,3)+F(1,6)"), C("5/6"), [
        D("3/6", 26985, "Adds the numerators and uses the larger denominator."),
        D("3/3", 26161, "Adds the numerators and uses the smaller denominator."),
        D("3/9", 15521, "Adds the denominators to get a common denominator."),
    ]),
    (425, "3/10 + 2/5 = ?", val("F(3,10)+F(2,5)"), C("7/10"), [
        D("5/10", 26985, "Adds the numerators and uses the larger denominator."),
        D("5/50", 18669, "Adds the numerators and multiplies the denominators."),
        D("6/50", 26157, "Multiplies numerators and denominators, treating + as x."),
    ]),
    # --- 426 Add, denominators share a common factor -------------------------
    (426, "Jo walks 1/4 of a mile to the shop and then 1/6 of a mile to the park. How far does she walk in total?", val("F(1,4)+F(1,6)"), C("5/12"), [
        D("1/12", 22562, "Finds the difference instead of the total."),
        D("2/10", 21651, "Adds numerators and adds denominators."),
    ]),
    (426, "A tank is 5/6 full. Then another 1/9 of a tank is added. What fraction of the tank is full now?", val("F(5,6)+F(1,9)"), C("17/18"), [
        D("13/18", 22562, "Finds the difference instead of the total."),
        D("6/15", 21651, "Adds numerators and adds denominators."),
    ]),
    (426, "Ali spends 3/8 of his money on a book and 1/6 of it on lunch. What fraction of his money does he spend in total?", val("F(3,8)+F(1,6)"), C("13/24"), [
        D("5/24", 22562, "Finds the difference instead of the total."),
        D("4/14", 21651, "Adds numerators and adds denominators."),
    ]),
    # --- 427 Add, denominators share no common factor ------------------------
    (427, "1/3 + 1/4 = ?", val("F(1,3)+F(1,4)"), C("7/12"), [
        D("7/24", 13807, "Converts to 4/12 + 3/12 correctly, then adds the denominators too."),
        D("2/7", 19849, "Adds numerators and adds denominators."),
        D("1/12", 26157, "Multiplies numerators and denominators, treating + as x."),
    ]),
    (427, "2/5 + 1/3 = ?", val("F(2,5)+F(1,3)"), C("11/15"), [
        D("9/15", 19088, "Multiplies both numerators by 3 when converting to fifteenths."),
        D("2/15", 16460, "Reads + as x."),
        D("3/15", 22639, "Changes the denominators to 15 but not the numerators."),
    ]),
    (427, "3/4 + 1/5 = ?", val("F(3,4)+F(1,5)"), C("19/20"), [
        D("4/9", 21651, "Adds numerators and adds denominators."),
        D("19/40", 13807, "Converts to 15/20 + 4/20 correctly, then adds the denominators too."),
        D("4/20", 22639, "Changes the denominators to 20 but not the numerators."),
    ]),
    # --- 3241 Missing-number fraction addition --------------------------------
    (3241, "? + 1/3 = 5/6. What is the missing fraction?", val("F(5,6)-F(1,3)"), C("1/2"), [
        D("4/3", 24501, "Subtracts numerators and denominators: (5-1)/(6-3)."),
        D("7/6", 14786, "Adds 5/6 + 1/3 instead of subtracting."),
    ]),
    (3241, "2/5 + ? = 9/10. What is the missing fraction?", val("F(9,10)-F(2,5)"), C("1/2"), [
        D("7/5", 24501, "Subtracts numerators and denominators: (9-2)/(10-5)."),
        D("13/10", 14786, "Adds 9/10 + 2/5 instead of subtracting."),
    ]),
    (3241, "? + 1/4 = 7/8. What is the missing fraction?", val("F(7,8)-F(1,4)"), C("5/8"), [
        D("6/4", 24501, "Subtracts numerators and denominators: (7-1)/(8-4)."),
        D("9/8", 14786, "Adds 7/8 + 1/4 instead of subtracting."),
    ]),
    # --- 432 Subtract proper fractions, same denominator ---------------------
    (432, "5/8 - 3/8 = ?", val("F(5,8)-F(3,8)"), C("2/8"), [
        D("2/16", 15931, "Subtracts the numerators and adds the denominators."),
        D("2", 19220, "Subtracts the numerators and thinks the denominators cancel."),
        D("15/8", 18356, "Multiplies the numerators."),
    ]),
    (432, "4/9 - 4/9 = ?", val("F(4,9)-F(4,9)"), C("0"), [
        D("1", 19221, "Believes a fraction minus itself is 1."),
        D("8/9", 19222, "Adds the numerators instead of subtracting."),
        D("1/9", 15932, "Divides the numerators: 4 / 4 = 1."),
    ]),
    (432, "7/10 - 2/10 = ?", val("F(7,10)-F(2,10)"), C("5/10"), [
        D("9/10", 19222, "Adds the numerators instead of subtracting."),
        D("5/20", 15931, "Subtracts the numerators and adds the denominators."),
        D("14/10", 18627, "Multiplies the numerators."),
    ]),
    # --- 433 Subtract, one denominator a multiple of the other ---------------
    (433, "3/4 - 1/2 = ?", val("F(3,4)-F(1,2)"), C("1/4"), [
        D("2/4", 14107, "Subtracts the numerators and keeps the largest denominator."),
        D("2/2", 24501, "Subtracts numerators and denominators: (3-1)/(4-2)."),
        D("4/6", 18369, "Adds numerators and adds denominators."),
    ]),
    (433, "5/6 - 1/3 = ?", val("F(5,6)-F(1,3)"), C("1/2"), [
        D("4/6", 14107, "Subtracts the numerators and keeps the largest denominator."),
        D("4/3", 24501, "Subtracts numerators and denominators: (5-1)/(6-3)."),
        D("7/6", 26054, "Treats the - sign as +."),
    ]),
    (433, "1/2 - 1/4 = ?", val("F(1,2)-F(1,4)"), C("1/4"), [
        D("1/2", 17587, "With the same numerators, subtracts the denominators: 1/(4-2)."),
        D("0/4", 14107, "Subtracts the numerators and keeps the largest denominator."),
        D("3/4", 26054, "Treats the - sign as +."),
    ]),
    # --- 434 Subtract, denominators share a common factor --------------------
    (434, "5/6 - 3/4 = ?", val("F(5,6)-F(3,4)"), C("1/12"), [
        D("2/2", 24501, "Subtracts numerators and denominators: (5-3)/(6-4)."),
        D("2/12", 26989, "Changes the denominators to 12 but not the numerators."),
    ]),
    (434, "7/10 - 1/4 = ?", val("F(7,10)-F(1,4)"), C("9/20"), [
        D("6/6", 24501, "Subtracts numerators and denominators: (7-1)/(10-4)."),
        D("6/20", 26989, "Changes the denominators to 20 but not the numerators."),
    ]),
    (434, "There is 5/6 of a cake. Mia eats some, and 1/4 of the cake is left. How much cake did Mia eat?", val("F(5,6)-F(1,4)"), C("7/12"), [
        D("13/12", 13954, "Confuses part and whole: adds 5/6 + 1/4."),
        D("4/2", 24501, "Subtracts numerators and denominators: (5-1)/(6-4)."),
        D("4/12", 26989, "Changes the denominators to 12 but not the numerators."),
    ]),
    # --- 435 Subtract, denominators share no common factor -------------------
    (435, "2/3 - 1/5 = ?", val("F(2,3)-F(1,5)"), C("7/15"), [
        D("-1/2", 24501, "Subtracts numerators and denominators: (2-1)/(3-5) = 1/-2.", stretch=True),
        D("1/15", 22639, "Changes the denominators to 15 but not the numerators."),
        D("1/8", 15521, "Adds the denominators to get a common denominator, keeps the numerators."),
    ]),
    (435, "How much bigger is 3/4 than 1/3?", val("F(3,4)-F(1,3)"), C("5/12"), [
        D("13/12", 27398, "Reads 'how much bigger' as asking for the total."),
        D("1/4", 18159, "Multiplies to find the difference: 3/4 x 1/3."),
        D("9/4", 18158, "Divides to find the difference: 3/4 / 1/3."),
    ]),
    (435, "1/2 - 1/3 = ?", val("F(1,2)-F(1,3)"), C("1/6"), [
        D("1", 17587, "With the same numerators, subtracts the denominators: 1/(3-2)."),
        D("0", 22639, "Changes the denominators to 6 but not the numerators: 1/6 - 1/6."),
        D("5/6", 26054, "Treats the - sign as +."),
    ]),
    # --- 436 Subtract mixed numbers, same denominator ------------------------
    (436, "3 5/7 - 2/7 = ?", val("3+F(5,7)-F(2,7)"), C("3 3/7"), [
        D("1 3/7", 15634, "Subtracts the 2 from the whole number and from the numerator."),
        D("1 5/7", 15635, "Subtracts the numerator 2 from the whole number only."),
        D("33/7", 26035, "Reads 3 5/7 as 35/7, then subtracts 2/7."),
    ]),
    (436, "5 4/6 - 3/6 = ?", val("5+F(4,6)-F(3,6)"), C("5 1/6"), [
        D("2 1/6", 15634, "Subtracts the 3 from the whole number and from the numerator."),
        D("2 4/6", 15635, "Subtracts the numerator 3 from the whole number only."),
        D("51/6", 26035, "Reads 5 4/6 as 54/6, then subtracts 3/6."),
    ]),
    (436, "6 7/8 - 4/8 = ?", val("6+F(7,8)-F(4,8)"), C("6 3/8"), [
        D("2 3/8", 15634, "Subtracts the 4 from the whole number and from the numerator."),
        D("2 7/8", 15635, "Subtracts the numerator 4 from the whole number only."),
        D("63/8", 26035, "Reads 6 7/8 as 67/8, then subtracts 4/8."),
    ]),
    # --- 437 Subtract mixed numbers, different denominators ------------------
    (437, "3 1/4 - 1 1/2 = ?", val("3+F(1,4)-1-F(1,2)"), C("1 3/4"), [
        D("2 1/4", 15098, "Gets 1/4 - 1/2 = -1/4 but writes 2 1/4 instead of taking 1/4 from 2."),
        D("2", 24501, "Subtracts numerators and denominators in the fraction part: 0/2."),
        D("4 3/4", 26054, "Treats the - sign as +."),
    ]),
    (437, "4 1/3 - 2 1/2 = ?", val("4+F(1,3)-2-F(1,2)"), C("1 5/6"), [
        D("2 1/6", 15098, "Gets 1/3 - 1/2 = -1/6 but writes 2 1/6 instead of taking 1/6 from 2."),
        D("6 5/6", 26054, "Treats the - sign as +."),
        D("2", 24501, "Subtracts numerators and denominators in the fraction part: 0/1."),
    ]),
    (437, "5 2/3 - 1 1/6 = ?", val("5+F(2,3)-1-F(1,6)"), C("4 1/2"), [
        D("4 1/3", 26161, "Subtracts the numerators and uses the smaller denominator."),
        D("6 5/6", 26054, "Treats the - sign as +."),
    ]),
    # --- 3328 Subtract an integer from a fraction, answer below 0 -----------
    (3328, "1/4 - 2 = ?", val("F(1,4)-2"), C("-1 3/4"), [
        D("-2 1/4", 16653, "Adds the sizes: 2 + 1/4, then makes it negative."),
        D("-3/4", 16655, "Gets the fraction part (3/4) but the whole part one too small, so the answer is 1 too big."),
        D("-1 1/4", 16656, "Keeps the original fraction part 1/4 below zero."),
    ]),
    (3328, "2/5 - 1 = ?", val("F(2,5)-1"), C("-3/5"), [
        D("-1 2/5", 16653, "Adds the sizes: 1 + 2/5, then makes it negative."),
        D("-2/5", 16656, "Keeps the original fraction part 2/5 below zero."),
        D("1/5", 16654, "Subtracts the integer from the numerator: (2-1)/5."),
    ]),
    (3328, "3/8 - 3 = ?", val("F(3,8)-3"), C("-2 5/8"), [
        D("-3 3/8", 16653, "Adds the sizes: 3 + 3/8, then makes it negative."),
        D("-1 5/8", 16655, "Gets the fraction part (5/8) but the whole part one too small, so the answer is 1 too big."),
        D("0", 16654, "Subtracts the integer from the numerator: (3-3)/8."),
    ]),
    # --- 3378 Times tables -----------------------------------------------------
    (3378, "7 x 8 = ?", val("7*8"), C("56"), [
        D("15", 15515, "Reads x as +."),
        D("1", 15627, "Subtracts instead of multiplying."),
    ]),
    (3378, "? x 6 = 42. What is the missing number?", val("F(42,6)"), C("7"), [
        D("252", 18289, "Multiplies the two numbers given."),
        D("36", 14138, "Uses an additive relationship: 42 - 6."),
    ]),
    (3378, "48 / 6 = ?", val("F(48,6)"), C("8"), [
        D("42", 15384, "Reads the division sign as subtract."),
        D("54", 22436, "Reads the division sign as add."),
    ]),
    # --- 342 Multiples ----------------------------------------------------------
    (342, "Which of these numbers is a multiple of 3?", {"kind": "predicate", "pred": "x % 3 == 0", "words": True}, C("27"), [
        D("13", 20492, "Believes multiples of 3 end in 3."),
        D("32", 22410, "Believes a number containing the digit 3 is a multiple of 3."),
        D("1", 13957, "Confuses factors and multiples: 1 is a factor of 3."),
    ]),
    (342, "Which of these numbers is a multiple of 4?", {"kind": "predicate", "pred": "x % 4 == 0", "words": True}, C("28"), [
        D("14", 18618, "Believes a number is a multiple of its final digit."),
        D("2", 13957, "Confuses factors and multiples: 2 is a factor of 4."),
        D("42", 22410, "Believes a number containing the digit 4 is a multiple of 4."),
    ]),
    (342, "What is the first multiple of 6?", val("6"), C("6"), [
        D("12", 15985, "Believes the first multiple of a is 2a."),
        D("1", 13957, "Confuses factors and multiples: 1 is a factor of 6."),
        D("36", 22136, "Confuses multiple with power: 6 squared."),
    ]),
    # --- 345 Lowest common multiple --------------------------------------------
    (345, "What is the lowest common multiple of 4 and 6?", val("lcm(4,6)"), C("12"), [
        D("24", 24069, "Multiplies the numbers together."),
        D("10", 15501, "Adds the numbers."),
        D("2", 15424, "Gives the HCF instead of the LCM."),
    ]),
    (345, "What is the lowest common multiple of 6 and 9?", val("lcm(6,9)"), C("18"), [
        D("54", 15500, "Uses the product of the numbers."),
        D("36", 15341, "Finds a common multiple but not the lowest."),
        D("9", 15969, "Believes the largest number is the LCM."),
    ]),
    (345, "What is the lowest common multiple of 8 and 12?", val("lcm(8,12)"), C("24"), [
        D("96", 24069, "Multiplies the numbers together."),
        D("48", 15341, "Finds a common multiple but not the lowest."),
        D("4", 15424, "Gives the HCF instead of the LCM."),
    ]),
    # --- 331 Factors -------------------------------------------------------------
    (331, "Which of these is a factor of 18?", {"kind": "predicate", "pred": "x.denominator == 1 and 18 % x == 0"}, C("6"), [
        D("36", 13957, "Confuses factors and multiples."),
        D("4", 16249, "Believes a factor of the final digit (8) is a factor of the number."),
        D("1.5", 18617, "Believes factors do not have to be integers."),
    ]),
    (331, "How many factors does 16 have?", val("ndiv(16)"), C("5"), [
        D("6", 14892, "Counts 4 twice because 4 x 4 = 16."),
        D("4", 21793, "Leaves out 16, believing a number can't divide itself."),
        D("8", 14338, "Gives an example of a factor instead of counting them."),
    ]),
    (331, "Which of these is NOT a factor of 24?", {"kind": "predicate", "pred": "24 % x != 0"}, C("9"), [
        D("1", 15423, "Believes 1 cannot be a factor."),
        D("24", 21793, "Believes a number cannot divide itself."),
    ]),
    # --- 338 Highest common factor ---------------------------------------------
    (338, "What is the highest common factor of 12 and 18?", val("gcd(12,18)"), C("6"), [
        D("2", 21713, "Gives a common factor, not the highest."),
        D("36", 15424, "Gives the LCM instead of the HCF."),
        D("30", 17605, "Adds the numbers."),
    ]),
    (338, "What is the highest common factor of 8 and 15?", val("gcd(8,15)"), C("1"), [
        D("0", 17611, "Believes that if there is no common factor other than 1, the answer is 0."),
        D("15", 15642, "Believes the largest number is the HCF."),
        D("120", 15424, "Gives the LCM instead of the HCF."),
    ]),
    (338, "What is the highest common factor of 16 and 24?", val("gcd(16,24)"), C("8"), [
        D("16", 15352, "Believes the smallest number is the HCF."),
        D("4", 21713, "Gives a common factor, not the highest."),
        D("40", 17605, "Adds the numbers."),
    ]),
    # --- 164 Mental division ---------------------------------------------------
    (164, "96 / 8 = ?", val("F(96,8)"), C("12"), [
        D("6", 16794, "Halves too many times: 96, 48, 24, 12, 6."),
        D("48", 18519, "Splits 8 into 2 x 4 but only divides by 2."),
        D("88", 15384, "Reads the division sign as subtract."),
    ]),
    (164, "84 / 4 = ?", val("F(84,4)"), C("21"), [
        D("24", 18384, "Divides only the tens digit: 8 / 4 = 2, keeps the 4."),
        D("81", 18085, "Divides only the ones digit: keeps the 8, 4 / 4 = 1."),
        D("80", 15384, "Reads the division sign as subtract."),
    ]),
    (164, "240 / 40 = ?", val("F(240,40)"), C("6"), [
        D("60", 22595, "Divides only by the significant digit: 240 / 4."),
        D("24", 18518, "Treats dividing by 40 like dividing by 10."),
        D("200", 15384, "Reads the division sign as subtract."),
    ]),
    # --- 3193 Express a division as a fraction --------------------------------
    (3193, "3 pizzas are shared equally between 4 people. How much pizza does each person get?", val("F(3,4)"), C("3/4"), [
        D("4/3", 26147, "Puts the number of sharers on top and the amount shared underneath."),
        D("0", 26992, "Thinks dividing by a larger number gives zero."),
        D("1/4", 15636, "Thinks 1/n describes sharing any number of items between n people."),
    ]),
    (3193, "Write 2 / 5 as a fraction.", val("F(2,5)"), C("2/5"), [
        D("5/2", 15004, "Divides the second number by the first."),
        D("1/5", 17978, "Believes all fractions have 1 as the numerator."),
        D("0", 26992, "Thinks dividing by a larger number gives zero."),
    ]),
    (3193, "Which fraction is equal to 7 / 3?", val("F(7,3)"), C("7/3"), [
        D("3/7", 15150, "Believes a fraction means dividing the denominator by the numerator."),
        D("4", 14839, "Subtracts instead of dividing: 7 - 3."),
    ]),
]


def build() -> list[dict]:
    questions, per_construct = [], {}
    for cid, text, check, correct, distractors in BANK:
        per_construct[cid] = per_construct.get(cid, 0) + 1
        qid = f"q-{cid}-{per_construct[cid]}"
        opts = [correct, *distractors]
        random.Random(qid).shuffle(opts)  # deterministic, so the correct key varies
        for key, o in zip("ABCD", opts):
            o["key"] = key
        questions.append({"id": qid, "construct_id": cid, "text": text, "check": check,
                          "options": [{"key": o.pop("key"), **o} for o in opts]})
    return questions


def seen_in_from_csv() -> dict[int, set[int]]:
    m = pd.read_csv(ROOT / "data" / "raw" / "misconception-map.csv")
    return m.groupby("ConstructId").MisconceptionId.apply(set).to_dict()


def main():
    questions = build()
    seen_in = seen_in_from_csv()
    failed = {q["id"]: e for q in questions if (e := verify_question(q, seen_in))}
    for qid, errs in failed.items():
        print(f"FAIL {qid}: {errs}")
    if failed:
        sys.exit(f"{len(failed)} questions failed verification; questions.json not written")
    (CURATED / "questions.json").write_text(json.dumps(questions, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(questions)} questions for {len({q['construct_id'] for q in questions})} constructs")


if __name__ == "__main__":
    main()
