<script setup lang="ts">
import { withBase } from 'vitepress'
const devices = [
  { name: 'Jetson Orin Nano', memory: '8 GB', file: 'orin', original: 'orin-original.jpg', role: 'Observation preprocessing · Request scheduling · LIBERO control' },
  { name: 'Jetson Thor', memory: '128 GB', file: 'thor', original: 'thor-original.jpg', role: 'Complete TurboVLA model · Action denormalization' }
]
</script>

<template>
  <div class="deployment-gallery">
    <figure v-for="device in devices" :key="device.file">
      <a :href="withBase(`/realpics/${device.file}-clean.jpg`)" target="_blank" rel="noopener">
        <img :src="withBase(`/realpics/${device.file}-clean.jpg`)" :alt="`${device.name} ${device.memory} deployed hardware; background-cleaned photograph`" width="1152" height="1536" loading="lazy">
      </a>
      <figcaption>
        <strong>{{ device.name }} <span>{{ device.memory }}</span></strong>
        <p>{{ device.role }}</p>
        <a :href="withBase(`/realpics/${device.original}`)" target="_blank" rel="noopener">View original photograph</a>
      </figcaption>
    </figure>
  </div>
  <p class="caption">Deployment photographs were cleaned with the DDS image API to remove background clutter and surface marks. Original photographs remain available. Device labels describe the deployment; performance is established by run records.</p>
</template>
