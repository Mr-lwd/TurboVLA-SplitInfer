<script setup lang="ts">
import { withBase } from 'vitepress'
const devices = [
  { name: 'Jetson Orin Nano', memory: '8 GB', file: 'orin', original: 'orin-original.jpg', role: '观测预处理 · 请求调度 · LIBERO 动作执行' },
  { name: 'Jetson Thor', memory: '128 GB', file: 'thor', original: 'thor-original.jpg', role: '完整 TurboVLA 模型 · 动作反归一化' }
]
</script>

<template>
  <div class="deployment-gallery">
    <figure v-for="device in devices" :key="device.file">
      <a :href="withBase(`/realpics/${device.file}-clean.jpg`)" target="_blank" rel="noopener">
        <img :src="withBase(`/realpics/${device.file}-clean.jpg`)" :alt="`${device.name} ${device.memory} 实际部署设备，实拍背景清理版`" width="1152" height="1536" loading="lazy">
      </a>
      <figcaption>
        <strong>{{ device.name }} <span>{{ device.memory }}</span></strong>
        <p>{{ device.role }}</p>
        <a :href="withBase(`/realpics/${device.original}`)" target="_blank" rel="noopener">查看原始实拍</a>
      </figcaption>
    </figure>
  </div>
  <p class="caption">实拍整理图：使用 DDS 图像接口清理背景杂物与表面污点，原图保留可核对。硬件容量与角色按项目部署信息标注；照片用于展示实际设备，性能结论以运行记录为准。</p>
</template>
