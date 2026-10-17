<script setup lang="ts">
import { useLocaleText } from './i18n'
const { t } = useLocaleText()

import { withBase } from 'vitepress'
</script>
<template><a :href="withBase('/downloads/turbovla-diagrams-editable.pptx')" download>{{ t("Download editable PowerPoint (2 slides)") }}</a></template>
