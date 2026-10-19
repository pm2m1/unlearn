# Pilot item review

Every question and every fixed sentence a pilot student can see is listed here. **The pilot uses an item only while its decision line reads `APPROVED`**; anything else (`PENDING`, `DROPPED`, `EDIT`) keeps it out. The pilot also refuses to create a class until the wording block is `APPROVED` and at least one session-1 and one session-2 check item are.

- **How to decide:** change `PENDING` after `**Decision:**` to `APPROVED` or `DROPPED`. For a change, write `EDIT` and a note on the same line; Claude Code applies the edit in `scripts/pilot_items.py` and the item comes back as `PENDING`. Anything after the decision word on that line is kept when the file is regenerated.
- **Fingerprints:** each block has a fingerprint of exactly what students see (stem, options, key, misconception tags). If the item changes, the fingerprint changes and an earlier decision no longer counts.
- **Regenerate:** `PYTHONPATH=api .venv/bin/python scripts/pilot_items.py` rewrites this file and keeps decisions whose fingerprint is unchanged.
- **Source:** copies of `data/curated/questions.json` with pilot-only edits; the demo's questions are not changed. Every item is re-checked by `verify_question` (maths and SEEN_IN) and the script refuses to write if one fails. Answer keys were also recomputed by hand in Phase 0.
- **Roles:** **S1** session-1 check, **S2** session-2 check (a different item on the same construct), **POOL** questions the Diagnoser and Tutor may ask in session 1. Check items are never asked by the Diagnoser or Tutor.

## Wording

### wording · fixed sentences and construct names

`fingerprint: 2b8354c70b`

From `api/unlearn/pilot/wording.py`. **The Hindi is a draft and needs a native speaker's check.**

**Assent screen (English, then Hindi):**

- **en** Before we start
  - This is a short maths activity about fractions. It takes about 20 minutes.
  - It is not a test, and it does not count for marks.
  - We save only your code and your answers, not your name.
  - You can stop at any time. Just close the page.
  - Button: Yes, I'm happy to do this
  - Button: I don't want to do this
  - After "no": That's fine. You don't have to do this. You can close this page.
- **hi** शुरू करने से पहले
  - यह भिन्नों (fractions) के बारे में गणित की एक छोटी गतिविधि है। इसमें लगभग 20 मिनट लगेंगे।
  - यह परीक्षा नहीं है, और इसके कोई अंक नहीं मिलेंगे।
  - हम सिर्फ़ आपका कोड और आपके उत्तर सहेजते हैं, आपका नाम नहीं।
  - आप कभी भी रुक सकते हैं। बस पेज बंद कर दें।
  - Button: हाँ, मैं तैयार हूँ
  - Button: नहीं, मुझे यह नहीं करना है
  - After "no": कोई बात नहीं। आपको यह करना ज़रूरी नहीं है। आप यह पेज बंद कर सकते हैं।

**Other sentences (English only):**

- `title`: Fractions practice
- `enter_code`: Type the code from your slip
- `start`: Start
- `bad_code`: That code didn't work. Check it with your teacher.
- `too_many`: Too many tries. Wait a minute, then try again.
- `warming`: Getting ready. Please wait a minute and try again.
- `ready`: Ready
- `not_open`: This activity is not open yet. Please ask your teacher.
- `check_intro`: Answer each question.
- `rule`: Give answers in simplest form, unless the question asks for an equivalent fraction.
- `more_intro`: Thank you! Now a few more questions to find what to practise.
- `progress`: Question {i} of {n}
- `practise_title`: Let's practise: {construct}
- `practise_teacher`: Your teacher will go through this with you.
- `practise_try`: Now try this one:
- `save_failed`: Your answer didn't save. Please tap Try again.
- `error`: Something went wrong. Please tap Try again.
- `try_again`: Try again
- `done_all_right`: Great work, you got them all right. That's all for today. Thank you!
- `done_s1`: That's all for today. Thank you!
- `wait_s2`: You have finished session 1. Your teacher will tell you when session 2 starts.
- `recall`: Last time we practised: {construct}.
- `recall_none`: Last time you didn't need extra practice.
- `done_s2`: That's all. Thank you for taking part!
- `finished`: You have finished both sessions. Thank you!

**Construct names a student may see** (after "Let's practise:" and in session 2's recall):

- 164 Carry out mental divisions when the answer is an integer
- 331 Identify factors of a number
- 338 Identify the Highest Common Factor of two numbers
- 342 Identify multiples of a number
- 345 Identify the Lowest Common Multiple of two numbers
- 408 Identify equivalent fractions when presented as shapes or objects
- 409 Identify equivalent fractions when presented as numbers
- 424 Add proper fractions with the same denominator
- 432 Subtract proper fractions with the same denominator
- 3342 Read fractions
- 3378 Know times tables up to 12 x 12

The Tutor's remediation skills are not shown to students: their steps are written as teacher instructions, so they appear only in the teacher view.

**Decision:** PENDING

## Check items

Session 1 asks the S1 items in this order; session 2 asks the S2 items. Each pair is on the same construct and shares at least one misconception tag.

### q-425-2 · S1 #1 · construct 425 Add proper fractions with different denominators where one is a multiple of the other

`fingerprint: b72c410bd3`

> 2/3 + 1/6 = ?

- A. `5/6`: **correct**
- B. `3/6`: 26985 Believes the denominator of the result is always the larger denominator when adding or subtracting fractions
- C. `3/3`: 26161 Believes the denominator of the result is always the smaller denominator when adding or subtracting fractions
- D. `3/9`: 15521 Believes adding the denominators gives a common denominator

**Decision:** PENDING

### q-425-3 · S2 #1 · construct 425 Add proper fractions with different denominators where one is a multiple of the other

`fingerprint: 9998f4e2bb`

> 3/10 + 2/5 = ?

- A. `5/10`: 26985 Believes the denominator of the result is always the larger denominator when adding or subtracting fractions
- B. `6/50`: 26157 Believes that adding fractions involves multiplying both the numerators and denominators, treating addition like multiplication
- C. `5/50`: 18669 When adding fractions, multiplies the denominators
- D. `7/10`: **correct**

**Decision:** PENDING

### q-427-1 · S1 #2 · construct 427 Add proper fractions with different denominators which do not share a common factor

`fingerprint: 6b720bd596`

> 1/3 + 1/4 = ?

- A. `1/12`: 26157 Believes that adding fractions involves multiplying both the numerators and denominators, treating addition like multiplication
- B. `2/7`: 19849 Thinks you add the numerators and add the denominators when adding fractions
- C. `7/12`: **correct**
- D. `7/24`: 13807 When adding fractions with unlike denominators, completes the first step correctly, but then adds the denominators in the final step

**Decision:** PENDING

### q-427-3 · S2 #2 · construct 427 Add proper fractions with different denominators which do not share a common factor

`fingerprint: ecc7800513`

> 3/4 + 1/5 = ?

- A. `19/20`: **correct**
- B. `19/40`: 13807 When adding fractions with unlike denominators, completes the first step correctly, but then adds the denominators in the final step
- C. `4/20`: 22639 Believes that only denominators need to be changed to create equivalent fractions, ignoring the numerators
- D. `4/9`: 21651 Believes that fractions are added by summing numerators and denominators as if they are separate whole numbers

**Decision:** PENDING

### q-433-1 · S1 #3 · construct 433 Subtract proper fractions with different denominators where one is a multiple of the other

`fingerprint: 811d973107`

> 3/4 - 1/2 = ?

- A. `2/2`: 24501 When subtracting fractions, believes you just subtract the numerators and subtract the denominators
- B. `4/6`: 18369 When subtracting fractions, adds the numerators and denominators
- C. `1/4`: **correct**
- D. `2/4`: 14107 Does not consider the denominator when adding/ subtracting fractions. Adds/subtracts the numerator and makes the denominator the one with the highest value

**Decision:** PENDING

### q-433-2 · S2 #3 · construct 433 Subtract proper fractions with different denominators where one is a multiple of the other

`fingerprint: 3a337e7e07`

> 5/6 - 1/3 = ?

- A. `1/2`: **correct**
- B. `7/6`: 26054 Believes that the subtraction sign in a calculation indicates addition rather than subtraction or negation
- C. `4/3`: 24501 When subtracting fractions, believes you just subtract the numerators and subtract the denominators
- D. `4/6`: 14107 Does not consider the denominator when adding/ subtracting fractions. Adds/subtracts the numerator and makes the denominator the one with the highest value

**Flag:** Key is 1/2 (3/6 simplified). Fine with the instruction "Give answers in simplest form, unless the question asks for an equivalent fraction".

**Decision:** PENDING

### q-435-1 · S1 #4 · construct 435 Subtract proper fractions with different denominators which do not share a common factor

`fingerprint: 4cdbdf01dd`

> 2/3 - 1/5 = ?

- A. `1/15`: 22639 Believes that only denominators need to be changed to create equivalent fractions, ignoring the numerators
- B. `1/8`: 15521 Believes adding the denominators gives a common denominator
- C. `7/15`: **correct**
- D. `13/15`: 26054 Believes that the subtraction sign in a calculation indicates addition rather than subtraction or negation

**Pilot edit:** Negative distractor -1/2 (24501) replaced by 13/15 (26054, adds instead of subtracting; SEEN_IN 435). (D was `-1/2` (24501))

**Suggested:** APPROVE the replacement distractor, or DROP (your default)

**Decision:** PENDING

### q-435-3 · S2 #4 · construct 435 Subtract proper fractions with different denominators which do not share a common factor

`fingerprint: 74018b397c`

> 1/2 - 1/3 = ?

- A. `1`: 17587 When subtracting fractions, believes that if the numerators are the same then you subtract the denominators
- B. `0`: 22639 Believes that only denominators need to be changed to create equivalent fractions, ignoring the numerators
- C. `1/6`: **correct**
- D. `5/6`: 26054 Believes that the subtraction sign in a calculation indicates addition rather than subtraction or negation

**Decision:** PENDING

### q-410-1 · S1 #5 · construct 410 Simplify fractions that simplify to a unit fraction

`fingerprint: 3d40aa1504`

> Simplify 4/12 fully.

- A. `4/12`: 15267 Does not recognise when a fraction can be simplified
- B. `1/3`: **correct**
- C. `1/4`: 15522 Believes when simplifying a fraction you can divide the numerator and denominator by different values
- D. `2/6`: 14537 Does not fully simplify fraction

**Decision:** PENDING

### q-410-2 · S2 #5 · construct 410 Simplify fractions that simplify to a unit fraction

`fingerprint: 4ca44bd10c`

> Simplify 6/24 fully.

- A. `3/12`: 14537 Does not fully simplify fraction
- B. `0.6/2.4`: 14110 Believes you can have decimals in a simplified fraction
- C. `1/6`: 15522 Believes when simplifying a fraction you can divide the numerator and denominator by different values
- D. `1/4`: **correct**

**Decision:** PENDING

## Diagnostic pool

### q-425-1 · POOL · construct 425 Add proper fractions with different denominators where one is a multiple of the other

`fingerprint: 3e5cb94c7f`

> 1/2 + 1/4 = ?

- A. `1/8`: 15031 When asked to add fractions, multiplies instead
- B. `1/6`: 14220 When adding fractions with identical numerators, leaves the numerator and adds the denominators
- C. `2/4`: 26989 Believes numerators stay the same when finding common denominators
- D. `3/4`: **correct**

**Decision:** PENDING

### q-427-2 · POOL · construct 427 Add proper fractions with different denominators which do not share a common factor

`fingerprint: c3a7e00216`

> 2/5 + 1/3 = ?

- A. `11/15`: **correct**
- B. `3/15`: 22639 Believes that only denominators need to be changed to create equivalent fractions, ignoring the numerators
- C. `2/15`: 16460 Thinks the plus sign means multiply
- D. `9/15`: 19088 When changing several fractions to have a common denominator, believes the numerators should all be multiplied by the same number

**Flag:** D "9/15" tagged 19088: the working (multiplies both numerators by 3) is plausible but unusual.

**Suggested:** Your call (tag on D)

**Decision:** PENDING

### q-433-3 · POOL · construct 433 Subtract proper fractions with different denominators where one is a multiple of the other

`fingerprint: 9a6a79f72c`

> 1/2 - 1/4 = ?

- A. `1/4`: **correct**
- B. `0/4`: 14107 Does not consider the denominator when adding/ subtracting fractions. Adds/subtracts the numerator and makes the denominator the one with the highest value
- C. `1/2`: 17587 When subtracting fractions, believes that if the numerators are the same then you subtract the denominators
- D. `3/4`: 26054 Believes that the subtraction sign in a calculation indicates addition rather than subtraction or negation

**Decision:** PENDING

### q-435-2 · POOL · construct 435 Subtract proper fractions with different denominators which do not share a common factor

`fingerprint: 1186c77fbe`

> How much bigger is 3/4 than 1/3?

- A. `9/4`: 18158 Believes that division should be used when asked to find the difference in a word problem
- B. `13/12`: 27398 Believes 'How much bigger' is asking for a total rather than a difference
- C. `1/4`: 18159 Believes multiplication should be used to find the difference in a word problem
- D. `5/12`: **correct**

**Decision:** PENDING

### q-410-3 · POOL · construct 410 Simplify fractions that simplify to a unit fraction

`fingerprint: bd9e49f554`

> Simplify 2 4/8 fully.

- A. `2 1/2`: **correct**
- B. `2 2/4`: 14537 Does not fully simplify fraction
- C. `1 1/2`: 14494 Simplifies integers when simplifying a mixed number
- D. `2 4/8`: 15074 Believes mixed numbers cannot be simplified

**Flag:** Simplifying a mixed number; option D repeats the question. Fine for Class 7, less sure for Class 6.

**Decision:** PENDING

### q-409-1 · POOL · construct 409 Identify equivalent fractions when presented as numbers

`fingerprint: 3ed204e6da`

> Which fraction is equivalent to 2/3?

- A. `1/2`: 20776 Thinks subtracting the same number from numerator and denominator creates equivalent fractions
- B. `8/12`: **correct**
- C. `4/3`: 22626 Believes that only numerators need to be changed to create equivalent fractions, ignoring the denominators
- D. `3/2`: 22644 Assumes that the numerator and denominator are not order-dependent, resulting in the belief that a/b is equivalent to b/a

**Flag:** The answer 8/12 is not in simplest form by design: the question asks for an equivalent fraction, which the instruction "Give answers in simplest form, unless the question asks for an equivalent fraction" exempts.

**Decision:** PENDING

### q-409-2 · POOL · construct 409 Identify equivalent fractions when presented as numbers

`fingerprint: d7069cc148`

> Which pair of fractions is equivalent?

- A. `3/5 and 5/7`: 23144 Thinks adding the same number to numerator and denominator creates equivalent fractions
- B. `1/3 and 2/6`: **correct**
- C. `2/5 and 2/9`: 17669 Thinks that fractions with the same numerator are equivalent
- D. `1/3 and 1/6`: 19786 Believes unit fractions are equivalent

**Pilot edit:** Grammar: "Which pair ... is". (stem was "Which pair of fractions are equivalent?")

**Decision:** PENDING

### q-409-3 · POOL · construct 409 Identify equivalent fractions when presented as numbers

`fingerprint: f556df0659`

> Find the missing number: 3/4 = ?/20

- A. `5`: 19414 When finding equivalent fractions, thinks the multiplier is the new numerator
- B. `15`: **correct**
- C. `3`: 22639 Believes that only denominators need to be changed to create equivalent fractions, ignoring the numerators
- D. `19`: 14007 Believes equivalent fractions are formed with addition not multiplication

**Decision:** PENDING

### q-345-1 · POOL · construct 345 Identify the Lowest Common Multiple of two numbers

`fingerprint: 81495dcda6`

> What is the lowest common multiple of 4 and 6?

- A. `2`: 15424 Confuses the calculations for HCF and LCM
- B. `10`: 15501 Believes adding two numbers finds their lowest common multiple
- C. `12`: **correct**
- D. `24`: 24069 Believes the lowest common multiple is found by multiplying the numbers together

**Decision:** PENDING

### q-345-2 · POOL · construct 345 Identify the Lowest Common Multiple of two numbers

`fingerprint: 079a3406de`

> What is the lowest common multiple of 6 and 9?

- A. `9`: 15969 Believes the largest number in a set of numbers is always their lowest common multiple
- B. `18`: **correct**
- C. `36`: 15341 Finds a common multiple but not the lowest common multiple
- D. `54`: 15500 Believes finding the product of two numbers gives their lowest common multiple

**Decision:** PENDING

### q-345-3 · POOL · construct 345 Identify the Lowest Common Multiple of two numbers

`fingerprint: a8df01f28a`

> What is the lowest common multiple of 8 and 12?

- A. `24`: **correct**
- B. `96`: 24069 Believes the lowest common multiple is found by multiplying the numbers together
- C. `4`: 15424 Confuses the calculations for HCF and LCM
- D. `48`: 15341 Finds a common multiple but not the lowest common multiple

**Decision:** PENDING

### q-342-1 · POOL · construct 342 Identify multiples of a number

`fingerprint: a75358009c`

> Which of these numbers is a multiple of 3?

- A. `1`: 13957 Confuses factors and multiples
- B. `32`: 22410 Believes that the presence of a digit in a number means it must be a multiple of that number
- C. `27`: **correct**
- D. `13`: 20492 Believes all multiples of 3 must end in 3

**Decision:** PENDING

### q-342-2 · POOL · construct 342 Identify multiples of a number

`fingerprint: ed035ee276`

> Which of these numbers is a multiple of 4?

- A. `42`: 22410 Believes that the presence of a digit in a number means it must be a multiple of that number
- B. `14`: 18618 Believes a number is always a multiple of its final digit
- C. `28`: **correct**
- D. `2`: 13957 Confuses factors and multiples

**Decision:** PENDING

### q-342-3 · POOL · construct 342 Identify multiples of a number

`fingerprint: 0199d14fa1`

> What is the first multiple of 6?

- A. `12`: 15985 Believes the first multiple of a is 2a
- B. `1`: 13957 Confuses factors and multiples
- C. `6`: **correct**
- D. `36`: 22136 Confuses the terms 'power' and 'multiple'

**Flag:** "First multiple of 6" = 6 matches NCERT; low risk.

**Decision:** PENDING

### q-424-1 · POOL · construct 424 Add proper fractions with the same denominator

`fingerprint: 9692377bc5`

> 2/7 + 3/7 = ?

- A. `5/7`: **correct**
- B. `5`: 19219 When adding fractions with the same denominator, believes they add the numerators and the denominators cancel out
- C. `6/7`: 21177 Thinks you multiply numerators when adding fractions with same denominator
- D. `5/14`: 21651 Believes that fractions are added by summing numerators and denominators as if they are separate whole numbers

**Decision:** PENDING

### q-424-2 · POOL · construct 424 Add proper fractions with the same denominator

`fingerprint: e28d79c8b2`

> 2/9 + 2/9 = ?

- A. `4/18`: 21651 Believes that fractions are added by summing numerators and denominators as if they are separate whole numbers
- B. `2/18`: 19192 When adding fractions with the same numerators, thinks you add the denominators and the numerator stays the same
- C. `4/81`: 15031 When asked to add fractions, multiplies instead
- D. `4/9`: **correct**

**Decision:** PENDING

### q-424-3 · POOL · construct 424 Add proper fractions with the same denominator

`fingerprint: f6aa6f641a`

> 1/5 + 3/5 = ?

- A. `4/5`: **correct**
- B. `3/10`: 18355 When adding fractions, thinks you add the denominators and multiply the numerators
- C. `4/6`: 19251 When adding fractions, believes they add the numerator of one addend to both the numerator and the denominator of the other addend
- D. `3/5`: 15032 Multiplies the numerators when adding fractions with a common denominator

**Decision:** PENDING

### q-432-1 · POOL · construct 432 Subtract proper fractions with the same denominator

`fingerprint: b72bb43b22`

> 5/8 - 3/8 = ?

- A. `1/4`: **correct**
- B. `15/8`: 18356 When subtracting fractions, thinks you multiply the numerators
- C. `2/16`: 15931 When subtracting fractions, subtracts the numerators and adds the denominators
- D. `2`: 19220 When subtracting fractions with the same denominator, believes they subtract the numerators and the denominators cancel out

**Pilot edit:** Correct option in simplest form (was 2/8), to match "Give answers in simplest form, unless the question asks for an equivalent fraction". (A was `2/8` (correct))

**Suggested:** APPROVE (your default: simplest form)

**Decision:** PENDING

### q-432-2 · POOL · construct 432 Subtract proper fractions with the same denominator

`fingerprint: d0e44f3341`

> 4/9 - 4/9 = ?

- A. `1`: 19221 Believes subtracting a fraction from itself results in 1
- B. `8/9`: 19222 When subtracting fractions, believes they add the numerators
- C. `1/9`: 15932 When subtracting fractions, divides the numerators
- D. `0`: **correct**

**Decision:** PENDING

### q-432-3 · POOL · construct 432 Subtract proper fractions with the same denominator

`fingerprint: cb079fea57`

> 7/10 - 2/10 = ?

- A. `14/10`: 18627 Believes subtraction of fractions involves multiplication of numerators
- B. `5/20`: 15931 When subtracting fractions, subtracts the numerators and adds the denominators
- C. `9/10`: 19222 When subtracting fractions, believes they add the numerators
- D. `1/2`: **correct**

**Pilot edit:** Correct option in simplest form (was 5/10), same rule. (D was `5/10` (correct))

**Suggested:** APPROVE (same rule as q-432-1)

**Decision:** PENDING

### q-338-1 · POOL · construct 338 Identify the Highest Common Factor of two numbers

`fingerprint: 32f2984364`

> What is the highest common factor of 12 and 18?

- A. `6`: **correct**
- B. `30`: 17605 Believes adding numbers together gives the highest common factor
- C. `2`: 21713 Believes that any common factor is sufficient and does not prioritize finding the greatest one
- D. `36`: 15424 Confuses the calculations for HCF and LCM

**Decision:** PENDING

### q-338-2 · POOL · construct 338 Identify the Highest Common Factor of two numbers

`fingerprint: 122700ae70`

> What is the highest common factor of 8 and 15?

- A. `120`: 15424 Confuses the calculations for HCF and LCM
- B. `1`: **correct**
- C. `0`: 17611 Believes that if there is no common factor other than 1, the answer is 0
- D. `15`: 15642 Believes the largest number in a set of numbers is always their highest common factor

**Decision:** PENDING

### q-338-3 · POOL · construct 338 Identify the Highest Common Factor of two numbers

`fingerprint: 157f3a0436`

> What is the highest common factor of 16 and 24?

- A. `8`: **correct**
- B. `40`: 17605 Believes adding numbers together gives the highest common factor
- C. `4`: 21713 Believes that any common factor is sufficient and does not prioritize finding the greatest one
- D. `16`: 15352 Believes the smallest number in a set of numbers is always their highest common factor

**Decision:** PENDING

### q-331-1 · POOL · construct 331 Identify factors of a number

`fingerprint: 2231186925`

> Which of these is a factor of 18?

- A. `6`: **correct**
- B. `1.5`: 18617 Believes factors do not have to be integers
- C. `4`: 16249 Thinks a factor of the final digit is also a factor of the whole number
- D. `36`: 13957 Confuses factors and multiples

**Decision:** PENDING

### q-331-2 · POOL · construct 331 Identify factors of a number

`fingerprint: b47f327451`

> How many factors does 16 have?

- A. `5`: **correct**
- B. `8`: 14338 Gives an example of a factor instead of counting how many total factors a number has
- C. `6`: 14892 Counts repeated factors as two separate factors
- D. `4`: 21793 Believes a number cannot divide itself evenly, ignoring the definition of factors

**Decision:** PENDING

### q-331-3 · POOL · construct 331 Identify factors of a number

`fingerprint: 0c63633d8c`

> Which of these is NOT a factor of 24?

- A. `9`: **correct**
- B. `1`: 15423 Believes 1 cannot be a factor of any number, rather than cannot be a prime factor
- C. `24`: 21793 Believes a number cannot divide itself evenly, ignoring the definition of factors

**Decision:** PENDING

### q-3342-1 · POOL · construct 3342 Read fractions

`fingerprint: f38c73f971`

> Which of these shows four sevenths?

- A. `4.7`: 15450 Believes a fraction and decimal are related such that numerator/denominator = numerator.denominator
- B. `4/7`: **correct**
- C. `7/4`: 14092 Mixes up the numerator and denominator
- D. `47`: 14014 Does not know how to write a fraction - just given an integer answer

**Decision:** PENDING

### q-3342-2 · POOL · construct 3342 Read fractions

`fingerprint: 501d0d8f85`

> Which fraction has a numerator of 2 and a denominator of 9?

- A. `2 1/9`: 14121 Uses numerator as whole part of a fraction
- B. `9/2`: 16784 Believes the denominator is the top of a fraction
- C. `2/9`: **correct**
- D. `29`: 14014 Does not know how to write a fraction - just given an integer answer

**Decision:** PENDING

### q-3342-3 · POOL · construct 3342 Read fractions

`fingerprint: dd3428d3c3`

> Which of these is equal to 7/3?

- A. `3/7`: 14092 Mixes up the numerator and denominator
- B. `2 1/3`: **correct**
- C. `7.3`: 15450 Believes a fraction and decimal are related such that numerator/denominator = numerator.denominator
- D. `7 1/3`: 21826 Believes an improper fraction a/b is equivalent to the mixed number a 1/b

**Pilot edit:** Stem said "Which mixed number", but two options aren't mixed numbers. (stem was "Which mixed number is equal to 7/3?")

**Suggested:** APPROVE the fixed stem, or DROP (your default)

**Decision:** PENDING

### q-3378-1 · POOL · construct 3378 Know times tables up to 12 x 12

`fingerprint: 0009237a76`

> 7 × 8 = ?

- A. `56`: **correct**
- B. `15`: 15515 Thinks the multiplication sign means to add
- C. `1`: 15627 Subtracts instead of multiplies

**Pilot edit:** × for multiplication. (stem was "7 x 8 = ?")

**Flag:** Only 3 options; 15 and 1 are weak distractors.

**Suggested:** DROP (your default)

**Decision:** PENDING

### q-3378-2 · POOL · construct 3378 Know times tables up to 12 x 12

`fingerprint: 405c60a044`

> ? × 6 = 42. What is the missing number?

- A. `36`: 14138 Confuses additive and multiplicative relationships
- B. `252`: 18289 If given two numbers in a multiplication equation, believes the task is to find their product
- C. `7`: **correct**

**Pilot edit:** × for multiplication. (stem was "? x 6 = 42. What is the missing number?")

**Suggested:** DROP (your default)

**Decision:** PENDING

### q-3378-3 · POOL · construct 3378 Know times tables up to 12 x 12

`fingerprint: ac65a1ed56`

> 48 ÷ 6 = ?

- A. `54`: 22436 Thinks the division sign represents addition
- B. `42`: 15384 Thinks the division sign means to subtract
- C. `8`: **correct**

**Pilot edit:** ÷ for division. (stem was "48 / 6 = ?")

**Suggested:** DROP (your default)

**Decision:** PENDING

### q-164-1 · POOL · construct 164 Carry out mental divisions when the answer is an integer

`fingerprint: 3c22075db1`

> 96 ÷ 8 = ?

- A. `12`: **correct**
- B. `6`: 16794 When dividing by 8 halves too many times
- C. `48`: 18519 When splitting a divisor into factors, does not realise they need to divide by all the factors
- D. `88`: 15384 Thinks the division sign means to subtract

**Pilot edit:** ÷ for division (Indian textbooks use ÷; "/" reads as a fraction). (stem was "96 / 8 = ?")

**Suggested:** APPROVE (your default: ÷ rendering)

**Decision:** PENDING

### q-164-2 · POOL · construct 164 Carry out mental divisions when the answer is an integer

`fingerprint: 883061619a`

> 84 ÷ 4 = ?

- A. `80`: 15384 Thinks the division sign means to subtract
- B. `21`: **correct**
- C. `81`: 18085 When dividing a 2 digit value with a 1 digit value, believes only the ones digit is divided
- D. `24`: 18384 When dividing a 2 digit value with a 1 digit value, believes only the tens digit is divided

**Pilot edit:** ÷ for division. (stem was "84 / 4 = ?")

**Suggested:** APPROVE (your default: ÷ rendering)

**Decision:** PENDING

### q-164-3 · POOL · construct 164 Carry out mental divisions when the answer is an integer

`fingerprint: d6ac00316e`

> 240 ÷ 40 = ?

- A. `24`: 18518 Confuses dividing by 10 with dividing by multiples of 10
- B. `200`: 15384 Thinks the division sign means to subtract
- C. `6`: **correct**
- D. `60`: 22595 Assumes that when dividing by a multiple of 10, you only need to divide by the significant digits

**Pilot edit:** ÷ for division. (stem was "240 / 40 = ?")

**Suggested:** APPROVE (your default: ÷ rendering)

**Decision:** PENDING
