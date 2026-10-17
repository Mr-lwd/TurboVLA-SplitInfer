<template>
  <div class="system-overview" aria-label="Device responsibilities">
    <section class="device orin">
      <h2>Jetson Orin Nano <span>8 GB</span></h2>
      <p>Observations, preprocessing and control</p>
      <ol><li>LIBERO dual-view observations</li><li>Image and state normalization</li><li>Tensor encoding and lossless compression</li><li>Action timeline and environment execution</li></ol>
    </section>
    <div class="transport"><span>Tensors + instruction →</span><strong>HTTP/1.1</strong><span>← 12 × 7 actions</span></div>
    <section class="device thor">
      <h2>Jetson Thor <span>128 GB</span></h2>
      <p>Complete neural inference</p>
      <ol><li>DINOv3 + online BERT</li><li>Bidirectional vision–language interaction</li><li>State projection + ACT decoding</li><li>Action denormalization and response</li></ol>
    </section>
  </div>
</template>
