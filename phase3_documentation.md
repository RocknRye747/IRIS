# Lift Bot: Phase 3 Documentation - Refined Pose Estimation and Ergonomic Risk Analyzer

## 1. Introduction

This document summarizes the enhancements made during Phase 3 of the Lift Bot development, focusing on refining the Pose Estimation and Ergonomic Risk Analyzer. The primary goal was to improve the accuracy and performance of the system by incorporating more detailed biomechanical considerations, investigating additional ergonomic risk factors, and exploring optimization strategies for the underlying pose estimation technology.

## 2. Enhanced Ergonomic Rules and Biomechanical Considerations

The `analyze_pose` function in `lift_bot_analyzer.py` has been significantly updated to include more granular and biomechanically informed risk assessments for key lifting postures. The enhancements cover:

### 2.1. Back Rounding (Spine Angle)

*   **Previous Approach:** A simpler angle calculation between mid-shoulder, mid-hip, and knee, with broad risk thresholds.
*   **Enhanced Approach:** The calculation now uses the angle between `mid_shoulder - mid_hip - mid_knee` to better approximate torso bend relative to the legs. Risk thresholds have been refined based on general ergonomic guidelines, penalizing significant forward bends (stooping) more heavily. For instance, angles greater than 120 degrees (indicating a very bent back) incur a higher penalty than moderate bends (90-120 degrees).
*   **Weighting:** The back risk factor now contributes 50% to the overall risk score, reflecting its critical importance in lifting ergonomics.

### 2.2. Straight-Leg Lifts (Knee Angle)

*   **Previous Approach:** Simple thresholds for knee angles to detect overly straight or overly bent legs.
*   **Enhanced Approach:** The knee angle calculation remains the same (`hip - knee - ankle`), but the risk assessment now more explicitly differentiates between stooping (legs too straight, `knee_angle > 160`) and squatting too deep (`knee_angle < 80`). Higher penalties are applied for straight-leg lifting, which is a common cause of back injury.
*   **Weighting:** Knee risk contributes 30% to the overall risk score.

### 2.3. Twisting Under Load (Shoulder-Hip Alignment)

*   **Previous Approach:** Calculated the angle between 2D shoulder and hip vectors.
*   **Enhanced Approach:** The method for detecting twisting remains based on the alignment of shoulder and hip vectors projected onto the XY plane. However, the risk thresholds have been adjusted to provide a more sensitive detection of significant twisting, with penalties increasing for deviations greater than 10-20 degrees from a straight alignment (0 or 180 degrees).
*   **Weighting:** Twist risk contributes 20% to the overall risk score.

### 2.4. Head/Neck Posture (New Factor)

*   **New Implementation:** An approximation for head/neck posture has been introduced. This calculates an angle using the `nose`, `mid_shoulder`, and a vertical reference point above the nose. This helps detect excessive forward or backward head tilt, which can contribute to musculoskeletal strain.
*   **Risk Calculation:** Penalties are applied for neck angles outside a healthy range (e.g., `> 100` for forward tilt, `< 70` for backward tilt).
*   **Weighting:** Neck risk contributes 10% to the overall risk score.

## 3. Integration of Additional Ergonomic Risk Factors

Beyond refining existing rules, the `analyze_pose` function now includes an approximation for **load distance** and acknowledges the conceptual need for **lift duration** and **asymmetry** as future enhancements.

### 3.1. Load Distance (Approximation)

*   **Implementation:** An approximation of the horizontal distance from the `mid-hip` to the `mid-wrist/hand` is calculated. This metric serves as an indicator of how far the load is held from the body, a critical factor in the NIOSH Lifting Equation. [1]
*   **Risk Calculation:** Risk increases as the `load_distance` (normalized within the image coordinates) increases, with thresholds defined to penalize loads held moderately or significantly far from the body.
*   **Weighting:** Load distance risk contributes 15% to the overall risk score.

### 3.2. Lift Duration (Conceptual)

*   **Consideration:** It was identified that `lift duration` cannot be accurately assessed within a single-frame analysis. This factor requires stateful tracking across multiple frames to detect the start and end of a lifting motion. It is noted as a crucial future enhancement for a more comprehensive ergonomic assessment.

### 3.3. Asymmetry (Refined Twisting)

*   **Consideration:** While the existing twist calculation serves as a proxy for asymmetry, a more explicit and robust asymmetry metric (e.g., based on the NIOSH Asymmetry Angle) would require more sophisticated 3D pose analysis and potentially multi-camera setups or specialized algorithms. The current twist metric is deemed sufficient for initial implementation, with further refinement planned.

## 4. Pose Estimation Optimization Strategies

Research was conducted to identify strategies for optimizing MediaPipe Pose processing for performance, particularly for edge deployments. The findings are detailed in the `pose_estimation_optimization.md` document [2] and include:

*   **Model Selection:** Utilizing MediaPipe's `lite` models for reduced computational overhead.
*   **Input Resolution:** Adjusting input image resolution to balance accuracy and speed.
*   **Confidence Thresholds:** Tuning `min_detection_confidence` and `min_tracking_confidence`.
*   **Feature Disablement:** Disabling `enable_segmentation` if not required.
*   **Hardware Acceleration:** Leveraging GPUs and TensorFlow Lite delegates for specialized edge hardware (e.g., NVIDIA Jetson, Google Coral).
*   **Pre- and Post-processing:** Optimizing image processing steps and output parsing.

These strategies will be crucial during the deployment phase to ensure Lift Bot operates efficiently in real-time on target hardware.

## 5. Testing Framework for Validation

To validate the accuracy and performance of these refinements, a robust testing framework has been designed, as detailed in `testing_framework_documentation.md` [3]. This framework outlines:

*   **Modules:** Data Ingestion, Pose Estimation, Ergonomic Analysis, Ground Truth Comparison, and Reporting.
*   **Dataset Requirements:** Emphasizing the need for diverse, high-quality, and meticulously annotated video sequences of lifting tasks with ground truth 3D pose landmarks and ergonomic classifications.
*   **Evaluation Metrics:** Defining metrics for pose estimation (MPJPE, PCK, OKS), ergonomic risk analysis (Accuracy, Precision, Recall, F1-Score, Confusion Matrix for classification; MAE, RMSE, Correlation for continuous scores), and system performance (FPS, Latency, CPU/GPU Utilization).

While the actual benchmarking and validation require an annotated dataset, the framework is in place to systematically assess the refined analyzer.

## 6. Conclusion

Phase 3 has significantly advanced the core analytical capabilities of Lift Bot. The `analyze_pose` function now incorporates a more nuanced understanding of ergonomic risks, including detailed biomechanical considerations for back, knee, twisting, and neck postures, along with an approximation for load distance. Coupled with identified optimization strategies and a defined testing framework, Lift Bot is well-positioned for accurate and efficient ergonomic monitoring.

## 7. References

[1] NIOSH Lifting Equation: [https://www.cdc.gov/niosh/ergonomics/about/RNLE.html](https://www.cdc.gov/niosh/ergonomics/about/RNLE.html)
[2] Lift Bot: Pose Estimation Optimization Strategies: [./pose_estimation_optimization.md](./pose_estimation_optimization.md)
[3] Lift Bot: Testing Framework and Dataset for Ergonomic Risk Analyzer: [./testing_framework_documentation.md](./testing_framework_documentation.md)

