# Portable Substance Identification Using Near-Infrared Spectroscopy

## Overview

Near-infrared (NIR) spectroscopy provides a **non-destructive, rapid, and reliable** method for material and substance identification based on molecular absorption characteristics. Recent advances in miniaturized optical and electronic components have enabled the development of **portable spectroscopic systems** suitable for field, laboratory, and educational use.

This repository contains the **software implementation** for a portable substance identification system based on the **Texas Instruments DLP NIRScan Nano**, operating in the **900–1700 nm** spectral range, combined with **machine learning–based classification**.

While baseline acquisition and classification pipelines are provided, the **primary objective of this repository is to enable the development and evaluation of improved data preprocessing techniques** for NIR spectra. Robust preprocessing is critical for improving classification accuracy, stability, and generalization in practical deployments.

---

## System Description

### Spectral Range and Hardware Platform

The selected **900–1700 nm** wavelength range captures important **overtone and combination absorption bands** of common molecular bonds such as:

- O–H  
- C–H  
- N–H  

These features make the range well-suited for distinguishing a wide variety of organic substances while maintaining:

- Low power consumption  
- Compact system size  
- Portability  

---

## Role of Data Preprocessing (Primary Focus)

Raw NIR spectra are highly sensitive to factors such as:

- Instrument drift  
- Reference instability  
- Scattering effects  
- Baseline shifts  
- Environmental noise  

As a result, **data preprocessing plays a decisive role** in downstream classification performance.

The **main goal of using and extending this repository is to design, implement, and evaluate improved preprocessing pipelines**, including but not limited to:

- Baseline correction  
- Smoothing and denoising  
- Normalization and scaling  
- Derivative spectroscopy  
- Wavelength selection or compression  

Users are encouraged to treat the provided preprocessing steps as **baselines**, not final solutions, and to experiment with alternative approaches to improve robustness and accuracy.

---

## Machine Learning–Based Classification

Due to the **high overlap and complexity of NIR spectral features**, classical threshold-based methods are insufficient for robust identification. This project therefore employs **supervised machine learning models** to:

1. Learn discriminative patterns from preprocessed NIR spectra  
2. Perform substance classification on new measurements  

The models are intentionally lightweight, allowing deployment on resource-constrained platforms such as the **Raspberry Pi**.

Experimental results demonstrate that the system can accurately identify target substances using **compact hardware and efficient computational models**, particularly when appropriate preprocessing is applied.

---

## Repository Scope

This repository focuses on the **software stack**, including:

- Spectral acquisition interfaces  
- Data preprocessing and normalization (**primary focus**)  
- Feature extraction  
- Model training and evaluation  
- Inference on newly acquired spectra  

Hardware assembly instructions are intentionally kept minimal and are described at a high level below.

---

## Using the Pre-Assembled Device (VGU)

If you are using the **readily assembled device prepared by Dr. Võ Bích Hiền at Vietnamese–German University (VGU)**, the setup is intentionally simple.

### Required Additional Components

You only need to purchase:

- **Two USB to Micro-USB data cables**

These are used for:
1. Connecting the **battery management circuit** to the **Raspberry Pi**
2. Connecting the **Raspberry Pi** to the **DLP NIRScan Nano**

No additional custom wiring should be required beyond these connections.

---

## Important Warnings and Notes

### ⚠ Lithium-Ion Battery Aging

The included **lithium-ion battery** may have experienced **capacity degradation due to age**, even if it has not been heavily used. As a result:

- Operating time may be significantly reduced  
- Sudden shutdowns during scans are possible  

It is recommended to:
- Test battery capacity before extended use  
- Replace the battery if unstable behavior is observed  

---

### ⚠ Reference Scan Obsolescence

The factory or previously stored **reference scan** on the device may be **obsolete**, which can lead to:

- Unstable measurements  
- Failed scans  
- Inconsistent classification results  

If scan failures or abnormal spectra are observed, you may need to **create a new reference scan**.

Please consult the **DLP NIRScan Nano User Guide** for detailed instructions on:
- Reference scan acquisition  
- Proper calibration procedures  

---

### ⚠ Enclosure Design Warning

The **current enclosure / casing** used for the system does **not allow proper mechanical and cable connections** between all components.

- The enclosure **should be redesigned** by the time you rely on this repository  
- If a redesigned enclosure is not available, **request or implement a redesign** before deployment  

Proper enclosure design is essential to:
- Avoid strained connectors  
- Ensure stable power delivery  
- Prevent accidental disconnections during scanning  

---

## Intended Audience

This repository is intended for:

- Students and researchers working with NIR spectroscopy  
- Engineers developing portable sensing systems  
- Educators demonstrating applied spectroscopy and machine learning  
- Developers focusing on **spectral data preprocessing and robustness**  

---

## Acknowledgment

I'd like to acknowledge Dr. Vo Bich Hien, Mr. Le Duy Nhat, as well as the DLP NIRScan Nano community on Github for providing us with assistance throughout this project.

---
