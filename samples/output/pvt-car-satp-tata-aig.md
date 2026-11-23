# Decision trace: pvt-car-satp-tata-aig.pdf

**Status:** `unsupported`

- **OD:** not applicable (Stand-alone TP policy: OD not applicable)
- **TP:** — (Tata AIG segment: The Tata AIG workbook has no make/model → segment table (all 7 sheets checked, hidden ones included), and the policy does not print a Tata AIG segment.)

**Confidence:** medium (2 of 3 facts the result used confirmed (67%); weakest link: insurer (verified both, page 12))

## Steps

1. **select**: Insurer Tata AIG, private car, satp policy: using the grid 'Tata AIG 'Pvtcar''.
   - Policy: `pvt-car-satp-tata-aig.pdf · page 12`
2. **date**: The policy date could not be read, so the grid's effective period (Standard Grid for Pvt Car LOB to be applicable from 1st Nov'25 policies) cannot be checked.
   - Grid: `raters/tata-aig/march-2026/Tata AIG Standard Grid_Communication_Mar'26_F_v2_0212.xlsx · 'Pvtcar'!F1`
3. **result**: Tata AIG segment: The Tata AIG workbook has no make/model → segment table (all 7 sheets checked, hidden ones included), and the policy does not print a Tata AIG segment.

## Facts

| Fact | Value | Page | Check | Confidence | Quote |
|---|---|---|---|---|---|
| addOns | Not found | — | not_found | unknown |  |
| bodyType | HATCHBACK | 4 | verified_both | medium | Body Type HATCHBACK |
| businessType | Not found | — | not_found | unknown |  |
| cc | 998 | 4 | verified_one | low | CC/KW 998 |
| cngLpgKitValue | 25.0 | 5 | verified_one | low | CNG / LPG kit TP (IMT 25 |
| cpaCover | Not found | — | not_found | unknown |  |
| fuel | cng | 4 | verified_one | low | Fuel Type CNG |
| gvw | Not found | — | not_found | unknown |  |
| insurer | belongs to Tata Sons Private Limited and AIG and is used by TATA AIG General Insurance Company Limited | 12 | verified_both | medium | belongs to Tata Sons Private Limited and AIG and is used by TATA AIG General Insurance Company Limited |
| issueDate | Not found | — | not_found | unknown |  |
| make | MARUTI | 4 | verified_both | medium | Make/Model/ MARUTI |
| manufactureYear | 2011 | 4 | confirmed_both | high | Mfg. Year 2011 |
| model | MARUTI/ZENESTILO/ | 4 | confirmed_both | high | Model/ MARUTI/ZENESTILO/ Mfg. Year 2011 |
| ncb | Not found | — | not_found | unknown |  |
| netPremium | 2154.0 | 5 | verified_one | low | Net Premium (B) 2154 |
| odPremium | Not found | — | not_found | unknown |  |
| odTermYears | Not found | — | not_found | unknown |  |
| policyStartDate | Not found | — | not_found | unknown |  |
| policyType | satp | 1 | confirmed_both | high | Liability Only Policy |
| powerKw | Not found | — | not_found | unknown |  |
| previousInsurer | Not found | — | not_found | unknown |  |
| previousNcb | Not found | — | not_found | unknown |  |
| registrationYear | 2011 | 4 | confirmed_both | high | Date of Registration 02/11/2011 |
| rto | DL09 | 4 | verified_one | low | Registration No. DL9CAB2893 |
| rtoLocation | DELHI | 4 | confirmed_both | high | RTO Location DELHI No |
| seatingCapacity | 5 | 4 | verified_one | low | Seating Capacity 5 |
| segment | Not found | — | not_found | unknown |  |
| tpPremium | 2154.0 | 5 | verified_one | low | Total Liability Premium (A) 2154 |
| tppdRestricted | Not found | — | not_found | unknown |  |
| vehicleClass | private_car | 4 | confirmed_both | high | Body Type HATCHBACK |

_Extractor: rules; OCR: {'rapidocr': '1.4.4', 'tesseract': '5.5.4'}; switches: {'BROKER_ELIGIBILITY': 'assume_base', 'GRID_DATE_POLICY': 'strict', 'LESSER_PERCENT_MEANS': 'points'}._
