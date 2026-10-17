<script setup lang="ts">
import { useLocaleText } from './i18n'
const { t } = useLocaleText()
</script>
<template>
  <div class="system-overview" :aria-label='t("Device responsibilities")'>
    <section class="device orin">
      <h2>Jetson Orin Nano <span>8 GB</span></h2>
      <p>{{ t("Observations, preprocessing and control") }}</p>
      <ol><li>{{ t("LIBERO dual-view observations") }}</li><li>{{ t("Image and state normalization") }}</li><li>{{ t("Tensor encoding and lossless compression") }}</li><li>{{ t("Action timeline and environment execution") }}</li></ol>
    </section>
    <div class="transport"><span>{{ t("Tensors + instruction →") }}</span><strong>HTTP/1.1</strong><span>{{ t("← 12 × 7 actions") }}</span></div>
    <section class="device thor">
      <h2>Jetson Thor <span>128 GB</span></h2>
      <p>{{ t("Complete neural inference") }}</p>
      <ol><li>{{ t("DINOv3 + online BERT") }}</li><li>{{ t("Bidirectional vision–language interaction") }}</li><li>{{ t("State projection + ACT decoding") }}</li><li>{{ t("Action denormalization and response") }}</li></ol>
    </section>
  </div>
</template>
