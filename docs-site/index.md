---
title: 项目概览
---

# 双设备推理，完整闭环

<p class="lead">TurboVLA-SplitInfer 将观测预处理与动作执行留在 Orin Nano 8GB，将完整神经网络放在 Thor 128GB，通过同步、异步替换与异步融合比较控制效果。</p>

<a class="primary-link" href="./guide/deployment.html">开始部署</a>
<a href="./guide/completeness.html">查看代码与验证链路</a>

<SystemOverview />

## 实物部署

项目已在 **Jetson Orin Nano 8GB 与 Jetson Thor 128GB** 两台实体设备上部署。下图为项目现场设备的实拍整理版，分别对应观测与控制端、完整模型推理端。

<DeploymentGallery />

部署步骤见[设备部署](./guide/deployment.md)，三种模式的运行结果按[验证与结果](./guide/validation.md)记录。

## 先理解拆分边界

跨设备传输的是**归一化图像、8 维状态和语言指令**。DINOv3、BERT、视觉语言交互、状态投影和 ACT 动作解码器全部在 Thor；Orin 不加载模型权重。返回值是可直接供 LIBERO 执行的 **12 × 7 动作块**。

本项目当前的双设备链路面向 **LIBERO 相对动作控制**。仓库保留 RoboTwin 训练与评测入口，但其三视角、50 步、14 维动作不适用于当前 split v1 协议。

## 用同一套输入比较三种调度

<TimelineDemo />

| 模式 | 要解决的问题 | 核心行为 |
| --- | --- | --- |
| Sync | 建立易解释的阻塞基线 | 用完动作块，再获取下一块 |
| Async / `replace` | 在动作执行期间进行推理 | 对齐新动作，替换未来时间线 |
| Blend | 减小新旧指令切换差异 | 对重叠区前六维渐变，夹爪离散切换 |

三种模式采用相同配置评测，通过成功率、控制间隔和往返延迟比较调度效果。

## 最短验证路径

1. 按[设备部署](./guide/deployment.md)准备依赖、模型与 LIBERO assets。
2. Thor 启动模型服务，Orin 执行 `--preflight` 检查。
3. 用单任务跑通三种模式，再扩大到多任务、多次试验。
4. 按[验证与结果](./guide/validation.md)核对成功率、控制间隔 p95、hold 与完整原始记录。

## 文档说明什么

| 需要了解 | 对应页面 |
| --- | --- |
| 两台设备分别运行什么、传输什么 | [双设备架构](./guide/architecture.md) |
| 动作如何对齐、何时融合、延迟时如何处理 | [调度机制](./guide/scheduling.md) |
| 代码、入口、配置与测试是否形成闭环 | [代码完整性](./guide/completeness.md) |
| 功能性、实时性、稳定性、安全性的实现与验证 | [系统能力](./guide/capabilities.md) |

本站提供代码入口、部署步骤、调度机制和结果分析方法。
