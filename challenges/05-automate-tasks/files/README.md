# Challenge 5: Automate a Task

## Data Files

The `reports/` folder contains monthly sales CSV files:

```
product,quantity,unit_price
Widget A,45,29.99
...
```

## Your Goal

Use `gh copilot suggest` to build `automate.sh` that:
1. Combines all CSV files
2. Calculates total revenue per product
3. Finds the top product
4. Saves a `summary.txt`

## Quick Reference

```bash
# Explore the data
ls reports/
cat reports/january.csv

# Ask Copilot for help
gh copilot suggest "combine CSV files and calculate revenue totals"
```
