# Decision trace: pvt-car-satp-go-digit.pdf

**Status:** `resolved`

- **OD:** not applicable (Stand-alone TP policy: OD not applicable)
- **TP:** 29.5% (insurer's published maximum (Max CD2)) · `raters/godigit/march-2026/Large Insurance Brokers Mar'26 - Shared.xlsx · '4W SATP'!E293`

**Confidence:** low (weakest link: cc (verified one, page 1))

## Steps

1. **select**: Insurer Go Digit, private car, satp policy: using the grid 'Go Digit '4W SATP''.
   - Policy: `pvt-car-satp-go-digit.pdf · page 1`
2. **date**: Grid 'Go Digit '4W SATP'': effective period not stated.
3. **map**: Go Digit RTO → 4WTP cluster: UP78 maps to UP_Bad.
   - Policy: `pvt-car-satp-go-digit.pdf · page 1`
   - Grid: `raters/godigit/march-2026/Large Insurance Brokers Mar'26 - Shared.xlsx · '4W  RTO'!B1609:C1609`
4. **match**: TP row matched (UP_Bad · Petrol>1000 · age All): 29.5% (insurer's published maximum (Max CD2)).
   - Policy: `pvt-car-satp-go-digit.pdf · page 1`
   - Grid: `raters/godigit/march-2026/Large Insurance Brokers Mar'26 - Shared.xlsx · '4W SATP'!E293`
5. **result**: Resolved: OD not applicable; TP 29.5%.
   - Grid: `raters/godigit/march-2026/Large Insurance Brokers Mar'26 - Shared.xlsx · '4W SATP'!E293`

## Facts

| Fact | Value | Page | Check | Confidence | Quote |
|---|---|---|---|---|---|
| addOns | Not found | — | not_found | unknown |  |
| bodyType | Not found | — | not_found | unknown |  |
| businessType | renewal | 2 | derived | medium | Previous Insurer GoDigitGeneral InsuranceLimited |
| cc | 1086 | 1 | verified_one | low | Engine No. G4HGKM999181 Chassis No. MALAF51CLKM049328 Cubic Capacity 1086CC |
| cngLpgKitValue | Not found | — | not_found | unknown |  |
| cpaCover | Not found | — | not_found | unknown |  |
| fuel | petrol | 1 | verified_both | medium | Fuel Type Petrol Year of Mfg. 0001-01-01 Year of Regn. 2019 |
| gvw | Not found | — | not_found | unknown |  |
| insurer | GoDigit General Insurance Ltd. | 1 | verified_both | medium | GoDigit General Insurance Ltd. Schedule/Certificate |
| issueDate | 2026-03-24 | 1 | verified_one | low | Policy No. D240744942 / 24031550 PolicyIssueDate 24-Mar-2026 Invoice No. IA224410314 |
| make | HYUNDAI | 1 | verified_both | medium | Make HYUNDAI Model/VehicleVariant(Sub-Type) SANTRONEW/1.1MT CORPORATE |
| manufactureYear | Not found | 1 | not_found | unknown | Fuel Type Petrol Year of Mfg. 0001-01-01 Year of Regn. 2019 |
| model | SANTRONEW/1.1MT CORPORATE | 1 | verified_both | medium | Make HYUNDAI Model/VehicleVariant(Sub-Type) SANTRONEW/1.1MT CORPORATE |
| ncb | Not found | — | not_found | unknown |  |
| netPremium | 3466.0 | 2 | verified_one | low | Net Premium ( 3466.00 |
| odPremium | Not found | — | not_found | unknown |  |
| odTermYears | Not found | — | not_found | unknown |  |
| policyStartDate | 2026-03-25 | 1 | verified_one | low | Period of Policy From 25-Mar-2026 00:00:01 InvoiceDate 24-Mar-2026 |
| policyType | satp | 1 | verified_both | medium | Digit Private Car Liability OnlyPolicy UINNo.:IRDAN158RP0002V01201718 |
| powerKw | Not found | — | not_found | unknown |  |
| previousInsurer | GoDigitGeneral InsuranceLimited | 2 | verified_both | medium | Previous Insurer GoDigitGeneral InsuranceLimited |
| previousNcb | Not found | — | not_found | unknown |  |
| registrationYear | 2019 | 1 | verified_both | medium | Fuel Type Petrol Year of Mfg. 0001-01-01 Year of Regn. 2019 |
| rto | UP78 | 1 | verified_one | low | Name REENA KUMARI VehicleRegistrationNo. UP78FZ1372 |
| rtoLocation | KANPUR NAGAR,UTTAR PRADESH | 1 | verified_one | low | RTOLocation Kanpur Nagar,UTTAR PRADESH Seating Capacity 5 |
| seatingCapacity | 5 | 1 | verified_one | low | RTOLocation Kanpur Nagar,UTTAR PRADESH Seating Capacity 5 |
| segment | Not found | — | not_found | unknown |  |
| tpPremium | Not found | — | not_found | unknown |  |
| tppdRestricted | Not found | — | not_found | unknown |  |
| vehicleClass | private_car | 1 | verified_both | medium | Digit Private Car Liability OnlyPolicy UINNo.:IRDAN158RP0002V01201718 |

_Extractor: rules; OCR: {'rapidocr': '1.4.4', 'tesseract': '5.5.4'}; switches: {'BROKER_ELIGIBILITY': 'assume_base', 'GRID_DATE_POLICY': 'strict', 'LESSER_PERCENT_MEANS': 'points'}._
