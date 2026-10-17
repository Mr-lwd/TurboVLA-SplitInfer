<template>
  <div class="system-overview" aria-label="双设备职责图">
    <section class="device orin">
      <h2>Jetson Orin Nano <span>8 GB</span></h2>
      <p>观测、预处理与控制</p>
      <ol><li>LIBERO 双视角观测</li><li>图像与状态归一化</li><li>张量编码、无损压缩</li><li>动作时间线与环境执行</li></ol>
    </section>
    <div class="transport"><span>张量 + 指令 →</span><strong>HTTP/1.1</strong><span>← 12 × 7 动作</span></div>
    <section class="device thor">
      <h2>Jetson Thor <span>128 GB</span></h2>
      <p>完整神经网络推理</p>
      <ol><li>DINOv3 + 在线 BERT</li><li>双向视觉语言交互</li><li>状态投影 + ACT 解码</li><li>动作反归一化与返回</li></ol>
    </section>
  </div>
</template>
