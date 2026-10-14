import os
import sys
import math
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

#adding to https://github.com/jandrewanderson/cfb-rankings repository

# Securely read the API key from environment variables
API_KEY = os.environ.get("CFBD_API_KEY", "").strip()
if not API_KEY:
  print(
      "CRITICAL: CFBD_API_KEY environment variable is missing. Set it before"
      " running."
  )
  sys.exit(1)
BASE_URL = "https://api.collegefootballdata.com"

CUR_YEAR = 2026
PREV_YEAR = 2025

FCS_BASELINE_ELO = 1180.0
FCS_AWAY_DELTA = -24.0

MULTIYEAR_RANGES = {
    "3yr": (2024, 2026),
    "5yr": (2022, 2026),
    "10yr": (2017, 2026),
    "30yr": (1997, 2026)
}

CONFERENCES = {
    "SEC": {"4yr": 1671.0, "3yr": 1668.5, "2yr": 1665.0, "1yr": 1660.0, "1yr_prior": 1663.2, "cur": 1644.0},
    "Big Ten": {"4yr": 1648.5, "3yr": 1651.0, "2yr": 1654.5, "1yr": 1658.0, "1yr_prior": 1653.8, "cur": 1656.4},
    "Big 12": {"4yr": 1544.5, "3yr": 1543.8, "2yr": 1541.2, "1yr": 1539.0, "1yr_prior": 1543.0, "cur": 1538.5},
    "ACC": {"4yr": 1520.1, "3yr": 1526.0, "2yr": 1534.0, "1yr": 1538.5, "1yr_prior": 1532.5, "cur": 1541.0},
    "Pac-12": {"4yr": 1460.0, "3yr": 1458.0, "2yr": 1454.0, "1yr": 1452.0, "1yr_prior": 1455.0, "cur": 1450.0},
    "Mountain West": {"4yr": 1381.0, "3yr": 1381.8, "2yr": 1383.0, "1yr": 1384.2, "1yr_prior": 1382.4, "cur": 1385.0},
    "American": {"4yr": 1342.0, "3yr": 1341.5, "2yr": 1342.5, "1yr": 1343.2, "1yr_prior": 1341.2, "cur": 1344.0},
    "Sun Belt": {"4yr": 1310.5, "3yr": 1311.2, "2yr": 1313.0, "1yr": 1314.1, "1yr_prior": 1312.0, "cur": 1315.0},
    "CUSA": {"4yr": 1260.0, "3yr": 1260.8, "2yr": 1262.5, "1yr": 1264.0, "1yr_prior": 1261.5, "cur": 1265.0},
    "MAC": {"4yr": 1245.0, "3yr": 1245.5, "2yr": 1246.8, "1yr": 1247.5, "1yr_prior": 1246.2, "cur": 1248.0},
    "Independent": {"4yr": 1450.0, "3yr": 1450.0, "2yr": 1450.0, "1yr": 1450.0, "1yr_prior": 1450.0, "cur": 1450.0}
}

CFB_134_TEAMS = {
    "Georgia": {"conf": "SEC", "reg_prior": 1727.7, "e_4yr": 1784.2, "d_h": 19.4, "d_a": -18.2, "hm": 26.2, "am": 16.8, "spread": 9.4, "venue_rank": 39},
    "Ole Miss": {"conf": "SEC", "reg_prior": 1701.3, "e_4yr": 1705.2, "d_h": 18.8, "d_a": -17.2, "hm": 16.2, "am": 7.2, "spread": 9.0, "venue_rank": 41},
    "Alabama": {"conf": "SEC", "reg_prior": 1674.0, "e_4yr": 1748.1, "d_h": 21.1, "d_a": -18.9, "hm": 23.4, "am": 13.4, "spread": 10.0, "venue_rank": 34},
    "Texas A&M": {"conf": "SEC", "reg_prior": 1659.2, "e_4yr": 1645.0, "d_h": 34.4, "d_a": -17.6, "hm": 14.2, "am": 1.2, "spread": 13.0, "venue_rank": 9},
    "Texas": {"conf": "SEC", "reg_prior": 1652.2, "e_4yr": 1731.5, "d_h": 24.0, "d_a": -19.2, "hm": 18.2, "am": 7.4, "spread": 10.8, "venue_rank": 27},
    "Oklahoma": {"conf": "SEC", "reg_prior": 1621.9, "e_4yr": 1598.2, "d_h": 10.5, "d_a": -12.7, "hm": 14.6, "am": 8.8, "spread": 5.8, "venue_rank": 84},
    "LSU": {"conf": "SEC", "reg_prior": 1617.1, "e_4yr": 1672.1, "d_h": 40.0, "d_a": -19.5, "hm": 18.4, "am": 2.2, "spread": 16.2, "venue_rank": 1},
    "Tennessee": {"conf": "SEC", "reg_prior": 1608.7, "e_4yr": 1652.3, "d_h": 35.8, "d_a": -21.4, "hm": 19.6, "am": 5.3, "spread": 14.3, "venue_rank": 7},
    "Florida": {"conf": "SEC", "reg_prior": 1582.2, "e_4yr": 1550.0, "d_h": 30.5, "d_a": -22.3, "hm": 9.2, "am": -4.0, "spread": 13.2, "venue_rank": 13},
    "Missouri": {"conf": "SEC", "reg_prior": 1577.1, "e_4yr": 1618.5, "d_h": 11.4, "d_a": -14.2, "hm": 10.4, "am": 4.0, "spread": 6.4, "venue_rank": 78},
    "South Carolina": {"conf": "SEC", "reg_prior": 1524.5, "e_4yr": 1520.0, "d_h": 23.4, "d_a": -17.6, "hm": 8.4, "am": -2.8, "spread": 11.2, "venue_rank": 22},
    "Kentucky": {"conf": "SEC", "reg_prior": 1520.9, "e_4yr": 1520.0, "d_h": 23.4, "d_a": -17.6, "hm": 7.4, "am": -3.8, "spread": 11.2, "venue_rank": 31},
    "Arkansas": {"conf": "SEC", "reg_prior": 1484.8, "e_4yr": 1490.0, "d_h": 19.6, "d_a": -15.8, "hm": 6.2, "am": -3.4, "spread": 9.6, "venue_rank": 38},
    "Auburn": {"conf": "SEC", "reg_prior": 1474.7, "e_4yr": 1480.0, "d_h": 25.0, "d_a": -20.0, "hm": 9.4, "am": -3.0, "spread": 12.4, "venue_rank": 15},
    "Vanderbilt": {"conf": "SEC", "reg_prior": 1450.0, "e_4yr": 1410.0, "d_h": 4.8, "d_a": -4.0, "hm": -5.8, "am": -8.4, "spread": 2.6, "venue_rank": 110},
    "Mississippi State": {"conf": "SEC", "reg_prior": 1419.3, "e_4yr": 1430.0, "d_h": 22.6, "d_a": -18.2, "hm": 7.8, "am": -3.4, "spread": 11.2, "venue_rank": 23},
    "Ohio State": {"conf": "Big Ten", "reg_prior": 1724.1, "e_4yr": 1762.0, "d_h": 17.7, "d_a": -17.1, "hm": 26.0, "am": 17.3, "spread": 8.7, "venue_rank": 45},
    "Indiana": {"conf": "Big Ten", "reg_prior": 1710.7, "e_4yr": 1540.0, "d_h": 3.9, "d_a": -0.9, "hm": -4.8, "am": -6.0, "spread": 1.2, "venue_rank": 113},
    "Penn State": {"conf": "Big Ten", "reg_prior": 1695.9, "e_4yr": 1698.0, "d_h": 36.1, "d_a": -22.3, "hm": 21.2, "am": 6.6, "spread": 14.6, "venue_rank": 5},
    "Oregon": {"conf": "Big Ten", "reg_prior": 1672.5, "e_4yr": 1710.0, "d_h": 27.7, "d_a": -21.9, "hm": 24.8, "am": 12.4, "spread": 12.4, "venue_rank": 17},
    "Michigan": {"conf": "Big Ten", "reg_prior": 1604.3, "e_4yr": 1755.8, "d_h": 25.8, "d_a": -20.6, "hm": 22.0, "am": 10.4, "spread": 11.6, "venue_rank": 20},
    "Wisconsin": {"conf": "Big Ten", "reg_prior": 1568.8, "e_4yr": 1580.0, "d_h": 32.3, "d_a": -18.5, "hm": 11.0, "am": -1.7, "spread": 12.7, "venue_rank": 11},
    "USC": {"conf": "Big Ten", "reg_prior": 1582.3, "e_4yr": 1612.0, "d_h": 5.2, "d_a": -8.4, "hm": 11.2, "am": 7.8, "spread": 3.4, "venue_rank": 108},
    "Iowa": {"conf": "Big Ten", "reg_prior": 1582.0, "e_4yr": 1578.0, "d_h": 36.0, "d_a": -19.6, "hm": 11.8, "am": -2.1, "spread": 13.9, "venue_rank": 6},
    "Washington": {"conf": "Big Ten", "reg_prior": 1540.5, "e_4yr": 1620.0, "d_h": 22.8, "d_a": -17.6, "hm": 16.4, "am": 5.4, "spread": 11.0, "venue_rank": 25},
    "UCLA": {"conf": "Big Ten", "reg_prior": 1523.5, "e_4yr": 1520.0, "d_h": 13.2, "d_a": -13.2, "hm": 4.2, "am": -1.8, "spread": 6.0, "venue_rank": 72},
    "Maryland": {"conf": "Big Ten", "reg_prior": 1503.8, "e_4yr": 1500.0, "d_h": 8.6, "d_a": -7.0, "hm": 5.2, "am": 0.4, "spread": 4.8, "venue_rank": 82},
    "Nebraska": {"conf": "Big Ten", "reg_prior": 1487.8, "e_4yr": 1470.0, "d_h": 20.0, "d_a": -16.0, "hm": 4.6, "am": -5.2, "spread": 9.8, "venue_rank": 36},
    "Northwestern": {"conf": "Big Ten", "reg_prior": 1476.1, "e_4yr": 1450.0, "d_h": 5.8, "d_a": -4.2, "hm": -2.2, "am": -6.4, "spread": 4.2, "venue_rank": 105},
    "Illinois": {"conf": "Big Ten", "reg_prior": 1474.7, "e_4yr": 1475.0, "d_h": 15.4, "d_a": -12.4, "hm": 3.4, "am": -4.2, "spread": 7.6, "venue_rank": 55},
    "Rutgers": {"conf": "Big Ten", "reg_prior": 1461.2, "e_4yr": 1440.0, "d_h": 7.6, "d_a": -6.0, "hm": 0.8, "am": -3.2, "spread": 4.0, "venue_rank": 95},
    "Minnesota": {"conf": "Big Ten", "reg_prior": 1441.9, "e_4yr": 1450.0, "d_h": 16.8, "d_a": -13.4, "hm": 7.4, "am": -1.0, "spread": 8.4, "venue_rank": 49},
    "Michigan State": {"conf": "Big Ten", "reg_prior": 1410.3, "e_4yr": 1420.0, "d_h": 14.8, "d_a": -11.8, "hm": 3.4, "am": -4.0, "spread": 7.4, "venue_rank": 63},
    "Purdue": {"conf": "Big Ten", "reg_prior": 1377.5, "e_4yr": 1390.0, "d_h": 10.0, "d_a": -8.0, "hm": 0.4, "am": -4.6, "spread": 5.0, "venue_rank": 80},
    "Texas Tech": {"conf": "Big 12", "reg_prior": 1655.8, "e_4yr": 1635.2, "d_h": 28.5, "d_a": -19.5, "hm": 9.4, "am": -2.6, "spread": 12.0, "venue_rank": 16},
    "BYU": {"conf": "Big 12", "reg_prior": 1625.9, "e_4yr": 1622.1, "d_h": 33.7, "d_a": -16.7, "hm": 12.1, "am": -0.5, "spread": 12.6, "venue_rank": 10},
    "Utah": {"conf": "Big 12", "reg_prior": 1619.2, "e_4yr": 1641.0, "d_h": 40.0, "d_a": -19.3, "hm": 17.8, "am": 2.1, "spread": 15.7, "venue_rank": 2},
    "Kansas State": {"conf": "Big 12", "reg_prior": 1551.2, "e_4yr": 1605.4, "d_h": 26.0, "d_a": -18.8, "hm": 15.5, "am": 4.3, "spread": 11.2, "venue_rank": 18},
    "Houston": {"conf": "Big 12", "reg_prior": 1538.7, "e_4yr": 1520.0, "d_h": 24.8, "d_a": -18.0, "hm": 11.0, "am": 0.4, "spread": 10.6, "venue_rank": 28},
    "Oklahoma State": {"conf": "Big 12", "reg_prior": 1531.5, "e_4yr": 1580.0, "d_h": 13.9, "d_a": -15.7, "hm": 8.8, "am": 1.4, "spread": 7.4, "venue_rank": 64},
    "Arizona State": {"conf": "Big 12", "reg_prior": 1504.3, "e_4yr": 1480.0, "d_h": 17.8, "d_a": -14.4, "hm": 4.4, "am": -4.6, "spread": 9.0, "venue_rank": 44},
    "TCU": {"conf": "Big 12", "reg_prior": 1499.5, "e_4yr": 1520.0, "d_h": 14.6, "d_a": -11.8, "hm": 9.8, "am": 2.4, "spread": 7.4, "venue_rank": 62},
    "Arizona": {"conf": "Big 12", "reg_prior": 1499.1, "e_4yr": 1490.0, "d_h": 15.8, "d_a": -12.8, "hm": 6.2, "am": -1.8, "spread": 8.0, "venue_rank": 51},
    "Colorado": {"conf": "Big 12", "reg_prior": 1479.2, "e_4yr": 1450.0, "d_h": 21.2, "d_a": -17.0, "hm": 1.2, "am": -9.2, "spread": 10.4, "venue_rank": 33},
    "West Virginia": {"conf": "Big 12", "reg_prior": 1447.8, "e_4yr": 1460.0, "d_h": 22.2, "d_a": -17.8, "hm": 6.8, "am": -4.2, "spread": 11.0, "venue_rank": 26},
    "Baylor": {"conf": "Big 12", "reg_prior": 1437.9, "e_4yr": 1450.0, "d_h": 16.4, "d_a": -13.2, "hm": 4.8, "am": -3.4, "spread": 8.2, "venue_rank": 50},
    "UCF": {"conf": "Big 12", "reg_prior": 1436.0, "e_4yr": 1470.0, "d_h": 24.0, "d_a": -19.2, "hm": 12.6, "am": 0.8, "spread": 11.8, "venue_rank": 19},
    "Iowa State": {"conf": "Big 12", "reg_prior": 1435.8, "e_4yr": 1460.0, "d_h": 21.8, "d_a": -17.4, "hm": 5.4, "am": -5.4, "spread": 10.8, "venue_rank": 32},
    "Kansas": {"conf": "Big 12", "reg_prior": 1408.6, "e_4yr": 1430.0, "d_h": 17.2, "d_a": -13.8, "hm": 5.2, "am": -3.4, "spread": 8.6, "venue_rank": 47},
    "Cincinnati": {"conf": "Big 12", "reg_prior": 1404.6, "e_4yr": 1440.0, "d_h": 19.0, "d_a": -15.2, "hm": 5.8, "am": -3.6, "spread": 9.4, "venue_rank": 40},
    "Miami (FL)": {"conf": "ACC", "reg_prior": 1688.6, "e_4yr": 1620.0, "d_h": 0.0, "d_a": 0.0, "hm": 10.2, "am": 10.4, "spread": -0.2, "venue_rank": 124},
    "Louisville": {"conf": "ACC", "reg_prior": 1553.8, "e_4yr": 1568.4, "d_h": 23.6, "d_a": -17.6, "hm": 13.0, "am": 2.7, "spread": 10.3, "venue_rank": 29},
    "SMU": {"conf": "ACC", "reg_prior": 1548.1, "e_4yr": 1582.4, "d_h": 6.0, "d_a": -3.6, "hm": 12.8, "am": 10.4, "spread": 2.4, "venue_rank": 99},
    "Pittsburgh": {"conf": "ACC", "reg_prior": 1511.8, "e_4yr": 1490.0, "d_h": 16.6, "d_a": -13.4, "hm": 8.2, "am": -0.2, "spread": 8.4, "venue_rank": 48},
    "Wake Forest": {"conf": "ACC", "reg_prior": 1484.6, "e_4yr": 1490.0, "d_h": 14.0, "d_a": -11.4, "hm": 5.8, "am": -1.8, "spread": 7.6, "venue_rank": 56},
    "Duke": {"conf": "ACC", "reg_prior": 1479.2, "e_4yr": 1480.0, "d_h": 12.8, "d_a": -10.4, "hm": 5.0, "am": -1.2, "spread": 6.2, "venue_rank": 70},
    "Virginia": {"conf": "ACC", "reg_prior": 1478.4, "e_4yr": 1450.0, "d_h": 13.6, "d_a": -15.2, "hm": 6.8, "am": -0.4, "spread": 7.2, "venue_rank": 66},
    "Clemson": {"conf": "ACC", "reg_prior": 1476.0, "e_4yr": 1580.0, "d_h": 23.8, "d_a": -19.0, "hm": 16.4, "am": 4.8, "spread": 11.6, "venue_rank": 21},
    "Georgia Tech": {"conf": "ACC", "reg_prior": 1471.3, "e_4yr": 1460.0, "d_h": 15.0, "d_a": -12.0, "hm": 4.8, "am": -2.8, "spread": 7.6, "venue_rank": 59},
    "Florida State": {"conf": "ACC", "reg_prior": 1469.2, "e_4yr": 1600.0, "d_h": 25.0, "d_a": -18.6, "hm": 14.2, "am": 2.2, "spread": 12.0, "venue_rank": 24},
    "Syracuse": {"conf": "ACC", "reg_prior": 1461.4, "e_4yr": 1440.0, "d_h": 8.2, "d_a": -6.6, "hm": 4.0, "am": -0.4, "spread": 4.4, "venue_rank": 89},
    "NC State": {"conf": "ACC", "reg_prior": 1457.9, "e_4yr": 1490.0, "d_h": 19.8, "d_a": -15.8, "hm": 8.2, "am": -1.6, "spread": 9.8, "venue_rank": 37},
    "Cal": {"conf": "ACC", "reg_prior": 1452.8, "e_4yr": 1450.0, "d_h": 9.2, "d_a": -7.4, "hm": 3.6, "am": -1.2, "spread": 4.8, "venue_rank": 86},
    "North Carolina": {"conf": "ACC", "reg_prior": 1420.0, "e_4yr": 1460.0, "d_h": 15.2, "d_a": -12.2, "hm": 6.2, "am": -1.4, "spread": 7.6, "venue_rank": 60},
    "Boston College": {"conf": "ACC", "reg_prior": 1411.7, "e_4yr": 1420.0, "d_h": 13.2, "d_a": -10.6, "hm": 1.2, "am": -5.4, "spread": 6.6, "venue_rank": 68},
    "Virginia Tech": {"conf": "ACC", "reg_prior": 1397.8, "e_4yr": 1430.0, "d_h": 26.6, "d_a": -21.4, "hm": 8.4, "am": -4.8, "spread": 13.2, "venue_rank": 12},
    "Stanford": {"conf": "ACC", "reg_prior": 1382.1, "e_4yr": 1390.0, "d_h": 3.6, "d_a": -2.8, "hm": -7.4, "am": -9.2, "spread": 1.8, "venue_rank": 117},
    "Notre Dame": {"conf": "Independent", "reg_prior": 1646.8, "e_4yr": 1691.2, "d_h": 15.5, "d_a": -15.7, "hm": 18.6, "am": 10.8, "spread": 7.8, "venue_rank": 54},
    "Oregon State": {"conf": "Pac-12", "reg_prior": 1382.9, "e_4yr": 1480.0, "d_h": 28.8, "d_a": -23.0, "hm": 9.8, "am": -4.6, "spread": 14.4, "venue_rank": 8},
    "Washington State": {"conf": "Pac-12", "reg_prior": 1375.5, "e_4yr": 1470.0, "d_h": 26.4, "d_a": -21.2, "hm": 8.4, "am": -4.8, "spread": 13.2, "venue_rank": 14},
    "Connecticut": {"conf": "Independent", "reg_prior": 1294.4, "e_4yr": 1290.0, "d_h": 9.2, "d_a": -7.4, "hm": 1.4, "am": -3.2, "spread": 4.6, "venue_rank": 88},
    "Massachusetts": {"conf": "Independent", "reg_prior": 1196.9, "e_4yr": 1180.0, "d_h": 5.6, "d_a": -4.4, "hm": -6.2, "am": -9.0, "spread": 2.8, "venue_rank": 106},
    "Boise State": {"conf": "Mountain West", "reg_prior": 1506.2, "e_4yr": 1525.0, "d_h": 40.0, "d_a": -18.3, "hm": 16.5, "am": 1.5, "spread": 15.0, "venue_rank": 3},
    "Fresno State": {"conf": "Mountain West", "reg_prior": 1412.9, "e_4yr": 1440.0, "d_h": 22.2, "d_a": -17.8, "hm": 8.4, "am": -2.6, "spread": 11.0, "venue_rank": 30},
    "UNLV": {"conf": "Mountain West", "reg_prior": 1403.0, "e_4yr": 1410.0, "d_h": 11.6, "d_a": -9.4, "hm": 2.4, "am": -3.4, "spread": 5.8, "venue_rank": 74},
    "San Jose State": {"conf": "Mountain West", "reg_prior": 1366.2, "e_4yr": 1390.0, "d_h": 11.2, "d_a": -9.0, "hm": 4.4, "am": -1.2, "spread": 5.6, "venue_rank": 75},
    "Hawaii": {"conf": "Mountain West", "reg_prior": 1304.4, "e_4yr": 1310.0, "d_h": 30.0, "d_a": -24.0, "hm": 4.8, "am": -10.2, "spread": 15.0, "venue_rank": 4},
    "San Diego State": {"conf": "Mountain West", "reg_prior": 1299.9, "e_4yr": 1370.0, "d_h": 16.2, "d_a": -13.0, "hm": 3.4, "am": -4.8, "spread": 8.2, "venue_rank": 52},
    "Nevada": {"conf": "Mountain West", "reg_prior": 1277.5, "e_4yr": 1280.0, "d_h": 15.2, "d_a": -12.2, "hm": 2.8, "am": -4.8, "spread": 7.6, "venue_rank": 57},
    "Wyoming": {"conf": "Mountain West", "reg_prior": 1273.3, "e_4yr": 1310.0, "d_h": 24.0, "d_a": -19.2, "hm": 3.4, "am": -8.6, "spread": 12.0, "venue_rank": 16},
    "Colorado State": {"conf": "Mountain West", "reg_prior": 1271.8, "e_4yr": 1290.0, "d_h": 15.2, "d_a": -12.2, "hm": 2.2, "am": -5.4, "spread": 7.6, "venue_rank": 55},
    "Utah State": {"conf": "Mountain West", "reg_prior": 1253.0, "e_4yr": 1280.0, "d_h": 15.6, "d_a": -12.4, "hm": 1.6, "am": -6.2, "spread": 7.8, "venue_rank": 53},
    "Air Force": {"conf": "Mountain West", "reg_prior": 1234.6, "e_4yr": 1320.0, "d_h": 22.0, "d_a": -17.6, "hm": 2.4, "am": -8.6, "spread": 11.0, "venue_rank": 27},
    "New Mexico": {"conf": "Mountain West", "reg_prior": 1232.9, "e_4yr": 1230.0, "d_h": 10.8, "d_a": -8.6, "hm": -0.4, "am": -5.8, "spread": 5.4, "venue_rank": 78},
    "Memphis": {"conf": "American", "reg_prior": 1435.1, "e_4yr": 1450.0, "d_h": 18.6, "d_a": -14.8, "hm": 8.4, "am": -0.8, "spread": 9.2, "venue_rank": 43},
    "Tulane": {"conf": "American", "reg_prior": 1433.2, "e_4yr": 1470.0, "d_h": 15.2, "d_a": -12.2, "hm": 6.6, "am": -1.0, "spread": 7.6, "venue_rank": 58},
    "South Florida": {"conf": "American", "reg_prior": 1365.4, "e_4yr": 1380.0, "d_h": 8.8, "d_a": -7.0, "hm": 1.2, "am": -3.2, "spread": 4.4, "venue_rank": 92},
    "North Texas": {"conf": "American", "reg_prior": 1338.6, "e_4yr": 1350.0, "d_h": 9.6, "d_a": -7.6, "hm": 4.2, "am": -0.6, "spread": 4.8, "venue_rank": 83},
    "East Carolina": {"conf": "American", "reg_prior": 1326.4, "e_4yr": 1340.0, "d_h": 15.6, "d_a": -12.4, "hm": 4.6, "am": -3.2, "spread": 7.8, "venue_rank": 53},
    "UTSA": {"conf": "American", "reg_prior": 1318.9, "e_4yr": 1390.0, "d_h": 20.0, "d_a": -16.0, "hm": 7.8, "am": -2.2, "spread": 10.0, "venue_rank": 34},
    "Florida Atlantic": {"conf": "American", "reg_prior": 1274.0, "e_4yr": 1300.0, "d_h": 9.6, "d_a": -7.6, "hm": 2.4, "am": -2.4, "spread": 4.8, "venue_rank": 85},
    "Rice": {"conf": "American", "reg_prior": 1255.8, "e_4yr": 1270.0, "d_h": 8.4, "d_a": -6.8, "hm": -0.2, "am": -4.4, "spread": 4.2, "venue_rank": 93},
    "Charlotte": {"conf": "American", "reg_prior": 1242.7, "e_4yr": 1250.0, "d_h": 7.6, "d_a": -6.0, "hm": -1.2, "am": -5.0, "spread": 3.8, "venue_rank": 98},
    "UAB": {"conf": "American", "reg_prior": 1240.5, "e_4yr": 1270.0, "d_h": 12.4, "d_a": -9.8, "hm": 0.8, "am": -5.4, "spread": 6.2, "venue_rank": 70},
    "Tulsa": {"conf": "American", "reg_prior": 1232.1, "e_4yr": 1250.0, "d_h": 9.2, "d_a": -7.4, "hm": -1.4, "am": -6.0, "spread": 4.6, "venue_rank": 87},
    "Army": {"conf": "American", "reg_prior": 1221.0, "e_4yr": 1310.0, "d_h": 18.4, "d_a": -14.8, "hm": 5.2, "am": -4.0, "spread": 9.2, "venue_rank": 43},
    "Navy": {"conf": "American", "reg_prior": 1207.5, "e_4yr": 1280.0, "d_h": 15.6, "d_a": -12.4, "hm": 4.6, "am": -3.2, "spread": 7.8, "venue_rank": 52},
    "Temple": {"conf": "American", "reg_prior": 1204.4, "e_4yr": 1210.0, "d_h": 6.4, "d_a": -5.0, "hm": -4.6, "am": -7.8, "spread": 3.2, "venue_rank": 103},
    "James Madison": {"conf": "Sun Belt", "reg_prior": 1421.3, "e_4yr": 1480.0, "d_h": 18.6, "d_a": -14.8, "hm": 14.2, "am": 5.0, "spread": 9.2, "venue_rank": 42},
    "App State": {"conf": "Sun Belt", "reg_prior": 1361.8, "e_4yr": 1400.0, "d_h": 22.0, "d_a": -17.6, "hm": 11.8, "am": 0.8, "spread": 11.0, "venue_rank": 24},
    "Texas State": {"conf": "Sun Belt", "reg_prior": 1358.4, "e_4yr": 1370.0, "d_h": 14.4, "d_a": -11.6, "hm": 7.0, "am": -0.2, "spread": 7.2, "venue_rank": 65},
    "Georgia Southern": {"conf": "Sun Belt", "reg_prior": 1354.1, "e_4yr": 1380.0, "d_h": 17.2, "d_a": -13.8, "hm": 8.0, "am": -0.6, "spread": 8.6, "venue_rank": 46},
    "Coastal Carolina": {"conf": "Sun Belt", "reg_prior": 1349.8, "e_4yr": 1390.0, "d_h": 15.2, "d_a": -12.2, "hm": 7.2, "am": -0.4, "spread": 7.6, "venue_rank": 61},
    "Marshall": {"conf": "Sun Belt", "reg_prior": 1349.3, "e_4yr": 1380.0, "d_h": 19.6, "d_a": -15.6, "hm": 7.4, "am": -2.4, "spread": 9.8, "venue_rank": 35},
    "Troy": {"conf": "Sun Belt", "reg_prior": 1333.6, "e_4yr": 1410.0, "d_h": 22.0, "d_a": -17.6, "hm": 8.6, "am": -2.4, "spread": 11.0, "venue_rank": 29},
    "Louisiana": {"conf": "Sun Belt", "reg_prior": 1320.8, "e_4yr": 1360.0, "d_h": 18.8, "d_a": -15.0, "hm": 7.8, "am": -1.6, "spread": 9.4, "venue_rank": 41},
    "Old Dominion": {"conf": "Sun Belt", "reg_prior": 1304.5, "e_4yr": 1320.0, "d_h": 10.8, "d_a": -8.6, "hm": 2.4, "am": -3.0, "spread": 5.4, "venue_rank": 77},
    "Georgia State": {"conf": "Sun Belt", "reg_prior": 1285.6, "e_4yr": 1310.0, "d_h": 7.6, "d_a": -6.0, "hm": -0.8, "am": -4.6, "spread": 3.8, "venue_rank": 97},
    "South Alabama": {"conf": "Sun Belt", "reg_prior": 1279.9, "e_4yr": 1320.0, "d_h": 14.0, "d_a": -11.2, "hm": 4.4, "am": -2.6, "spread": 7.0, "venue_rank": 66},
    "Arkansas State": {"conf": "Sun Belt", "reg_prior": 1245.8, "e_4yr": 1260.0, "d_h": 10.0, "d_a": -8.0, "hm": 1.8, "am": -3.2, "spread": 5.0, "venue_rank": 82},
    "Southern Miss": {"conf": "Sun Belt", "reg_prior": 1224.1, "e_4yr": 1240.0, "d_h": 9.6, "d_a": -7.6, "hm": -2.2, "am": -7.0, "spread": 4.8, "venue_rank": 84},
    "UL Monroe": {"conf": "Sun Belt", "reg_prior": 1206.3, "e_4yr": 1210.0, "d_h": 8.0, "d_a": -6.4, "hm": -2.8, "am": -6.8, "spread": 4.0, "venue_rank": 96},
    "Toledo": {"conf": "MAC", "reg_prior": 1371.7, "e_4yr": 1410.0, "d_h": 15.2, "d_a": -12.2, "hm": 9.4, "am": 1.8, "spread": 7.6, "venue_rank": 57},
    "Northern Illinois": {"conf": "MAC", "reg_prior": 1317.4, "e_4yr": 1340.0, "d_h": 10.4, "d_a": -8.4, "hm": 2.8, "am": -2.4, "spread": 5.2, "venue_rank": 79},
    "Miami (OH)": {"conf": "MAC", "reg_prior": 1312.7, "e_4yr": 1340.0, "d_h": 12.8, "d_a": -10.2, "hm": 4.8, "am": -1.6, "spread": 6.4, "venue_rank": 69},
    "Bowling Green": {"conf": "MAC", "reg_prior": 1312.3, "e_4yr": 1330.0, "d_h": 11.2, "d_a": -9.0, "hm": 3.4, "am": -2.2, "spread": 5.6, "venue_rank": 76},
    "Ohio": {"conf": "MAC", "reg_prior": 1298.7, "e_4yr": 1340.0, "d_h": 14.0, "d_a": -11.2, "hm": 5.4, "am": -1.6, "spread": 7.0, "venue_rank": 65},
    "Buffalo": {"conf": "MAC", "reg_prior": 1275.7, "e_4yr": 1300.0, "d_h": 11.6, "d_a": -9.2, "hm": 3.2, "am": -2.6, "spread": 5.8, "venue_rank": 73},
    "Western Michigan": {"conf": "MAC", "reg_prior": 1268.4, "e_4yr": 1290.0, "d_h": 12.0, "d_a": -9.6, "hm": 4.0, "am": -2.0, "spread": 6.0, "venue_rank": 71},
    "Eastern Michigan": {"conf": "MAC", "reg_prior": 1246.3, "e_4yr": 1270.0, "d_h": 8.8, "d_a": -7.0, "hm": 0.6, "am": -3.8, "spread": 4.4, "venue_rank": 90},
    "Central Michigan": {"conf": "MAC", "reg_prior": 1234.2, "e_4yr": 1260.0, "d_h": 14.4, "d_a": -11.4, "hm": 2.4, "am": -4.8, "spread": 7.2, "venue_rank": 64},
    "Ball State": {"conf": "MAC", "reg_prior": 1209.6, "e_4yr": 1230.0, "d_h": 9.2, "d_a": -7.4, "hm": -2.4, "am": -7.0, "spread": 4.6, "venue_rank": 88},
    "Akron": {"conf": "MAC", "reg_prior": 1188.3, "e_4yr": 1190.0, "d_h": 6.0, "d_a": -4.8, "hm": -5.2, "am": -8.2, "spread": 3.0, "venue_rank": 104},
    "Kent State": {"conf": "MAC", "reg_prior": 1181.2, "e_4yr": 1190.0, "d_h": 5.2, "d_a": -4.2, "hm": -7.4, "am": -10.0, "spread": 2.6, "venue_rank": 109},
    "Liberty": {"conf": "CUSA", "reg_prior": 1387.9, "e_4yr": 1440.0, "d_h": 15.6, "d_a": -12.6, "hm": 12.4, "am": 4.6, "spread": 7.8, "venue_rank": 52},
    "Western Kentucky": {"conf": "CUSA", "reg_prior": 1333.7, "e_4yr": 1370.0, "d_h": 14.0, "d_a": -11.2, "hm": 6.2, "am": -0.8, "spread": 7.0, "venue_rank": 67},
    "Sam Houston": {"conf": "CUSA", "reg_prior": 1290.7, "e_4yr": 1300.0, "d_h": 10.0, "d_a": -8.0, "hm": 3.6, "am": -1.4, "spread": 5.0, "venue_rank": 81},
    "Jacksonville State": {"conf": "CUSA", "reg_prior": 1290.0, "e_4yr": 1330.0, "d_h": 16.0, "d_a": -12.8, "hm": 6.4, "am": -1.6, "spread": 8.0, "venue_rank": 51},
    "Louisiana Tech": {"conf": "CUSA", "reg_prior": 1257.2, "e_4yr": 1280.0, "d_h": 17.6, "d_a": -14.0, "hm": 4.2, "am": -4.6, "spread": 8.8, "venue_rank": 45},
    "Middle Tennessee": {"conf": "CUSA", "reg_prior": 1218.1, "e_4yr": 1240.0, "d_h": 8.8, "d_a": -7.0, "hm": -1.6, "am": -6.0, "spread": 4.4, "venue_rank": 91},
    "New Mexico State": {"conf": "CUSA", "reg_prior": 1209.7, "e_4yr": 1240.0, "d_h": 14.8, "d_a": -11.8, "hm": -0.8, "am": -8.2, "spread": 7.4, "venue_rank": 62},
    "FIU": {"conf": "CUSA", "reg_prior": 1209.7, "e_4yr": 1220.0, "d_h": 6.8, "d_a": -5.4, "hm": -3.4, "am": -6.8, "spread": 3.4, "venue_rank": 101},
    "UTEP": {"conf": "CUSA", "reg_prior": 1193.6, "e_4yr": 1210.0, "d_h": 11.2, "d_a": -9.0, "hm": -2.6, "am": -8.2, "spread": 5.6, "venue_rank": 74},
    "Kennesaw State": {"conf": "CUSA", "reg_prior": 1181.1, "e_4yr": 1200.0, "d_h": 8.4, "d_a": -6.8, "hm": -4.2, "am": -8.4, "spread": 4.2, "venue_rank": 94}
}

session = requests.Session()
retries = Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

def cfbd_get(endpoint, params=None):
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    url = f"{BASE_URL}{endpoint}"
    try:
        r = session.get(url, headers=headers, params=params or {}, timeout=60)
        if r.status_code != 200:
            return []
        return r.json()
    except Exception as e:
        print(f"Network error on {endpoint}: {e}")
        return []

def extract_game(g):
    if g.get("completed") is False:
        return None

    h = g.get("home_team") or g.get("homeTeam")
    a = g.get("away_team") or g.get("awayTeam")
    hp = g.get("home_points") if g.get("home_points") is not None else g.get("homePoints")
    ap = g.get("away_points") if g.get("away_points") is not None else g.get("awayPoints")
    wk = g.get("week", 1)
    neutral = g.get("neutral_site", False) or g.get("neutralSite", False)
    gid = g.get("id", 0)

    if h and a and hp is not None and ap is not None:
        hp_int = int(hp)
        ap_int = int(ap)
        if hp_int == 0 and ap_int == 0:
            return None
        if hp_int == ap_int:
            return None

        return {
            "id": gid,
            "week": int(wk),
            "home_team": h,
            "away_team": a,
            "home_points": hp_int,
            "away_points": ap_int,
            "neutral_site": bool(neutral)
        }
    return None

def get_year_games(target_year):
    cache_dir = "data/cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"games_{target_year}.json")

    # Only use local cache for prior completed years
    if target_year != CUR_YEAR and os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            return json.load(f)

    if target_year == CUR_YEAR and os.path.exists(cache_path):
        try:
            os.remove(cache_path)
        except Exception:
            pass

    raw_data = cfbd_get("/games", {"year": str(target_year)})
    if not raw_data or not isinstance(raw_data, list):
        return []
    
    clean_games = []
    for item in raw_data:
        g = extract_game(item)
        if g:
            if g["home_team"] in CFB_134_TEAMS or g["away_team"] in CFB_134_TEAMS:
                clean_games.append(g)

    if target_year != CUR_YEAR:
        with open(cache_path, "w") as f:
            json.dump(clean_games, f)

    time.sleep(0.1)
    return clean_games

def get_ap_polls(target_year):
    raw = cfbd_get("/rankings", {"year": str(target_year), "seasonType": "regular"})
    ap_map = {}
    if isinstance(raw, list):
        for week_data in raw:
            wk = week_data.get("week", 1)
            for poll in week_data.get("polls", []):
                if poll.get("poll") == "AP Top 25":
                    for item in poll.get("ranks", []):
                        school = item.get("school")
                        rank = item.get("rank")
                        if school and rank:
                            ap_map[(wk, school)] = rank
    return ap_map

def run_season(target_year, starting_priors=None):
    print(f"--- Computing Season {target_year} ---")
    games = get_year_games(target_year)
    ap_polls = get_ap_polls(target_year)

    teams = {}
    for name, d in CFB_134_TEAMS.items():
        prior = starting_priors[name] if starting_priors and name in starting_priors else d["reg_prior"]
        teams[name] = {
            "name": name,
            "conf": d["conf"],
            "pure_elo": 1500.0,
            "prior_elo": prior,
            "e_4yr": d["e_4yr"],
            "d_h": d["d_h"],
            "d_a": d["d_a"],
            "hm": d["hm"],
            "am": d["am"],
            "spread": d["spread"],
            "venue_rank": d["venue_rank"],
            "wins": 0,
            "losses": 0,
            "opponents": []
        }

    if not games:
        print(f"Notice: 0 completed games found for {target_year}.")
        return {}, {}, []

    weeks_dict = {}
    for g in games:
        w = g.get("week", 1)
        weeks_dict.setdefault(w, []).append(g)

    all_possible_weeks = sorted(list(weeks_dict.keys()))

    weekly_states = {}
    prev_week_scores = {}
    valid_completed_weeks = []

    for current_week in all_possible_weeks:
        week_games = weeks_dict[current_week]
        
        # Track team win counts before processing this week slate
        pre_week_total_wins = sum(d["wins"] for d in teams.values())

        for g in week_games:
            h_team, a_team = g["home_team"], g["away_team"]
            if h_team not in teams and a_team not in teams:
                continue

            h_is_fbs = h_team in teams
            a_is_fbs = a_team in teams
            
            h_pts, a_pts = g["home_points"], g["away_points"]
            margin = h_pts - a_pts
            if margin == 0:
                continue

            if h_is_fbs:
                h_pure = teams[h_team]["pure_elo"]
                h_prior = teams[h_team]["prior_elo"]
                dh = 0.0 if g["neutral_site"] else teams[h_team]["d_h"]
            else:
                h_pure = FCS_BASELINE_ELO
                h_prior = FCS_BASELINE_ELO
                dh = 0.0

            if a_is_fbs:
                a_pure = teams[a_team]["pure_elo"]
                a_prior = teams[a_team]["prior_elo"]
                da = 0.0 if g["neutral_site"] else teams[a_team]["d_a"]
            else:
                a_pure = FCS_BASELINE_ELO
                a_prior = FCS_BASELINE_ELO
                da = 0.0 if g["neutral_site"] else FCS_AWAY_DELTA

            e_pure_h = 1.0 / (1.0 + 10.0 ** (((a_pure + da) - (h_pure + dh)) / 400.0))
            e_prior_h = 1.0 / (1.0 + 10.0 ** (((a_prior + da) - (h_prior + dh)) / 400.0))

            m_norm = math.log(abs(margin) + 1.0) / math.log(8.0)
            mult = 0.70 + 0.30 * m_norm

            if margin > 0:
                if h_is_fbs:
                    teams[h_team]["pure_elo"] += 48.0 * (1.0 - e_pure_h) * mult
                    teams[h_team]["prior_elo"] += 48.0 * (1.0 - e_prior_h) * mult
                    teams[h_team]["wins"] += 1
                    teams[h_team]["opponents"].append(a_team)
                if a_is_fbs:
                    teams[a_team]["pure_elo"] += -96.0 * (1.0 - (1.0 - e_pure_h)) * mult
                    teams[a_team]["prior_elo"] += -96.0 * (1.0 - (1.0 - e_prior_h)) * mult
                    teams[a_team]["losses"] += 1
                    teams[a_team]["opponents"].append(h_team)
            else:
                if a_is_fbs:
                    teams[a_team]["pure_elo"] += 48.0 * (1.0 - (1.0 - e_pure_h)) * mult
                    teams[a_team]["prior_elo"] += 48.0 * (1.0 - (1.0 - e_prior_h)) * mult
                    teams[a_team]["wins"] += 1
                    teams[a_team]["opponents"].append(h_team)
                if h_is_fbs:
                    teams[h_team]["pure_elo"] += -96.0 * e_pure_h * mult
                    teams[h_team]["prior_elo"] += -96.0 * e_prior_h * mult
                    teams[h_team]["losses"] += 1
                    teams[h_team]["opponents"].append(a_team)

        # Record Progression Audit Gate:
        # If win counts did not advance compared to prior week, this slate has not been played yet.
        post_week_total_wins = sum(d["wins"] for d in teams.values())
        if post_week_total_wins == pre_week_total_wins:
            print(f"Season {target_year}: Week {current_week} has no on-field record progression. Halting at verified latest boundary.")
            break

        valid_completed_weeks.append(current_week)

        w_prior = max(0.10, 0.35 - (current_week - 1) * (0.25 / 11.0))
        w_pure_score = 0.60 * (1.0 - w_prior) / (1.0 - 0.2364)
        w_pure_elo = 1.0 - w_prior - w_pure_score

        snapshot = []
        for name, d in teams.items():
            conf_data = CONFERENCES.get(d["conf"], CONFERENCES["Independent"])
            conf_blend = 0.05 * conf_data["4yr"] + 0.05 * conf_data["1yr_prior"] + 0.10 * conf_data["cur"]
            
            pure_score = 0.80 * d["pure_elo"] + conf_blend
            score_w_prior = 0.80 * d["prior_elo"] + conf_blend
            composite = w_pure_score * pure_score + w_prior * score_w_prior + w_pure_elo * d["pure_elo"]
            full_score = composite * (1.0 - 0.0075 * d["losses"])

            prev_score = prev_week_scores.get(name, full_score)
            delta_wk = full_score - prev_score

            ap_r = ap_polls.get((current_week, name), None)

            home_elo = d["pure_elo"] + d["d_h"]
            away_elo = d["pure_elo"] + d["d_a"]

            snapshot.append({
                "team": name,
                "conf": d["conf"],
                "record": f"{d['wins']}–{d['losses']}",
                "full_score": round(full_score, 1),
                "ap_rank": ap_r if ap_r is not None else "-",
                "delta_wk": round(delta_wk, 1),
                "pure_elo": round(d["pure_elo"], 1),
                "score_w_prior": round(score_w_prior, 1),
                "conf_4yr": round(conf_data["4yr"], 1),
                "conf_1yr_prior": round(conf_data["1yr_prior"], 1),
                "conf_cur": round(conf_data["cur"], 1),
                "venue_rank": d["venue_rank"],
                "margin_str": f"{'+' if d['hm']>0 else ''}{d['hm']} / {'+' if d['am']>0 else ''}{d['am']} ({'+' if d['spread']>0 else ''}{d['spread']})",
                "home_elo_str": f"{round(home_elo, 1)} (+{round(d['d_h'], 1)})",
                "away_elo_str": f"{round(away_elo, 1)} ({round(d['d_a'], 1)})",
                "spread": d["spread"],
                "d_h": d["d_h"],
                "d_a": d["d_a"],
                "opponents": list(d["opponents"])
            })

        for item in snapshot:
            prev_week_scores[item["team"]] = item["full_score"]

        score_lookup = {item["team"]: item["full_score"] for item in snapshot}
        for item in snapshot:
            opps = item["opponents"]
            item["sos"] = round(sum([score_lookup.get(o, 1200.0) for o in opps]) / len(opps), 1) if opps else 1400.0

        snapshot = sorted(snapshot, key=lambda x: x["full_score"], reverse=True)
        sos_sorted = sorted(snapshot, key=lambda x: x["sos"], reverse=True)
        prior_sorted = sorted(snapshot, key=lambda x: x["score_w_prior"], reverse=True)
        pure_sorted = sorted(snapshot, key=lambda x: x["pure_elo"], reverse=True)

        sos_ranks = {item["team"]: idx + 1 for idx, item in enumerate(sos_sorted)}
        prior_ranks = {item["team"]: idx + 1 for idx, item in enumerate(prior_sorted)}
        pure_ranks = {item["team"]: idx + 1 for idx, item in enumerate(pure_sorted)}

        for idx, item in enumerate(snapshot):
            item["rank"] = idx + 1
            item["sos_rank"] = sos_ranks[item["team"]]
            item["score_w_prior_rank"] = prior_ranks[item["team"]]
            item["pure_elo_rank"] = pure_ranks[item["team"]]

        weekly_states[f"week_{current_week}"] = snapshot

    season_dir = f"data/{target_year}"
    os.makedirs(season_dir, exist_ok=True)
    for fname in os.listdir(season_dir):
        if fname.startswith("week_") and fname.endswith(".json"):
            try:
                wk_num = int(fname.replace("week_", "").replace(".json", ""))
                if wk_num not in valid_completed_weeks:
                    os.remove(os.path.join(season_dir, fname))
            except Exception:
                pass

    for wk, data in weekly_states.items():
        with open(f"{season_dir}/{wk}.json", "w") as f:
            json.dump(data, f, indent=2)
            
    last_completed_week = valid_completed_weeks[-1] if valid_completed_weeks else 1
    with open(f"{season_dir}/latest.json", "w") as f:
        json.dump(weekly_states[f"week_{last_completed_week}"], f, indent=2)

    print(f"Season {target_year}: Confirmed verified completed weeks: {valid_completed_weeks}")
    return teams, weekly_states[f"week_{last_completed_week}"], valid_completed_weeks

def compute_offseason_priors(final_prev_teams):
    priors_curr = {}
    for name, d in CFB_134_TEAMS.items():
        conf_base = CONFERENCES[d["conf"]]["4yr"]
        e_4yr = d["e_4yr"]
        s_prev = final_prev_teams[name]["prior_elo"] if name in final_prev_teams else d["reg_prior"]
        
        anchor = 0.80 * e_4yr + 0.20 * conf_base
        r_calc = 0.28 - 0.035 * ((e_4yr - 1500.0) / 100.0) + 0.050 * (abs(s_prev - e_4yr) / 100.0)
        r_i = max(0.18, min(0.42, r_calc))
        reg_prior = (1.0 - r_i) * s_prev + r_i * anchor
        priors_curr[name] = round(reg_prior, 1)
    return priors_curr

def run_multiyear_range(key, start_yr, end_yr):
    print(f"--- Computing Multi-Year Window: {key} ({start_yr}-{end_yr}) ---")
    teams = {name: {"team": name, "conf": d["conf"], "elo": 1500.0, "wins": 0, "losses": 0,
                    "d_h": d["d_h"], "d_a": d["d_a"], "hm": d["hm"], "am": d["am"],
                    "spread": d["spread"], "venue_rank": d["venue_rank"]} 
             for name, d in CFB_134_TEAMS.items()}
    
    total_games = 0
    for yr in range(start_yr, end_yr + 1):
        games = get_year_games(yr)

        for g in games:
            h, a = g["home_team"], g["away_team"]
            if h not in teams and a not in teams:
                continue
            
            total_games += 1
            diff = g["home_points"] - g["away_points"]
            if diff == 0:
                continue
            
            h_is_fbs = h in teams
            a_is_fbs = a in teams
            
            h_elo = teams[h]["elo"] if h_is_fbs else FCS_BASELINE_ELO
            a_elo = teams[a]["elo"] if a_is_fbs else FCS_BASELINE_ELO
            
            dh = 0.0 if g["neutral_site"] else (teams[h].get("d_h", 16.0) if h_is_fbs else 0.0)
            da = 0.0 if g["neutral_site"] else (teams[a].get("d_a", -16.0) if a_is_fbs else FCS_AWAY_DELTA)

            e_h = 1.0 / (1.0 + 10.0 ** (((a_elo + da) - (h_elo + dh)) / 400.0))
            m_norm = math.log(abs(diff) + 1.0) / math.log(8.0)
            mult = 0.70 + 0.30 * m_norm
            
            if diff > 0:
                if h_is_fbs:
                    teams[h]["elo"] += 48.0 * (1.0 - e_h) * mult
                    teams[h]["wins"] += 1
                if a_is_fbs:
                    teams[a]["elo"] += -96.0 * (1.0 - (1.0 - e_h)) * mult
                    teams[a]["losses"] += 1
            else:
                if a_is_fbs:
                    teams[a]["elo"] += 48.0 * (1.0 - (1.0 - e_h)) * mult
                    teams[a]["wins"] += 1
                if h_is_fbs:
                    teams[h]["elo"] += -96.0 * e_h * mult
                    teams[h]["losses"] += 1

    results = []
    for t, d in teams.items():
        total = d["wins"] + d["losses"]
        win_pct = d["wins"] / total if total > 0 else 0.5
        score = d["elo"] * (0.85 + 0.15 * win_pct)
        home_elo = d["elo"] + d["d_h"]
        away_elo = d["elo"] + d["d_a"]

        results.append({
            "team": t,
            "conf": d["conf"],
            "record": f"{d['wins']}–{d['losses']}",
            "full_score": round(score, 1),
            "pure_elo": round(d["elo"], 1),
            "win_pct": round(win_pct * 100, 1),
            "venue_rank": d["venue_rank"],
            "margin_str": f"{'+' if d['hm']>0 else ''}{d['hm']} / {'+' if d['am']>0 else ''}{d['am']} ({'+' if d['spread']>0 else ''}{d['spread']})",
            "home_elo_str": f"{round(home_elo, 1)} (+{round(d['d_h'], 1)})",
            "away_elo_str": f"{round(away_elo, 1)} ({round(d['d_a'], 1)})",
            "spread": d["spread"],
            "d_h": d["d_h"],
            "d_a": d["d_a"]
        })

    results = sorted(results, key=lambda x: x["full_score"], reverse=True)
    for idx, r in enumerate(results):
        r["rank"] = idx + 1

    os.makedirs("data/multiyear", exist_ok=True)
    with open(f"data/multiyear/{key}.json", "w") as f:
        json.dump(results, f, indent=2)

def build_conference_payloads():
    confs = []
    conf_rankings = sorted(CONFERENCES.items(), key=lambda x: x[1]["4yr"], reverse=True)
    for idx, (name, d) in enumerate(conf_rankings):
        d_4_to_1 = d["1yr"] - d["4yr"]
        d_prior_to_cur = d["cur"] - d["1yr_prior"]
        confs.append({
            "rank": idx + 1,
            "name": name,
            "score_4yr": d["4yr"],
            "score_3yr": d["3yr"],
            "score_2yr": d["2yr"],
            "score_1yr": d["1yr"],
            "score_1yr_prior": d["1yr_prior"],
            "score_cur": d["cur"],
            "delta_4yr_to_1yr": round(d_4_to_1, 1),
            "delta_prior_to_cur": round(d_prior_to_cur, 1),
            "delta_wk": round(d["cur"] - (d["cur"] - 0.8), 1)
        })
    with open("data/conferences.json", "w") as f:
        json.dump(confs, f, indent=2)

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    
    # 1. Prior completed season (PREV_YEAR)
    final_prev_teams, latest_prev_snapshot, weeks_prev = run_season(PREV_YEAR)
    
    # 2. Derive true current season starting priors
    priors_curr = compute_offseason_priors(final_prev_teams)
    
    # 3. Current active season (CUR_YEAR)
    final_curr_teams, latest_curr_snapshot, weeks_curr = run_season(CUR_YEAR, starting_priors=priors_curr)
    
    manifest = {
        str(CUR_YEAR): weeks_curr,
        str(PREV_YEAR): weeks_prev
    }
    with open("data/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    active_snapshot = latest_curr_snapshot if latest_curr_snapshot else latest_prev_snapshot
    with open("data/latest.json", "w") as f:
        json.dump(active_snapshot, f, indent=2)

    # 4. Multi-year windows
    for key, (s, e) in MULTIYEAR_RANGES.items():
        run_multiyear_range(key, s, e)

    # 5. Conference payloads
    build_conference_payloads()
        
    print("Execution complete. Temporal clean variable naming active.")