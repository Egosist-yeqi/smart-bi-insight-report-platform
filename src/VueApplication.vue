<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue';

const legacyWorkspace = ref(null);
let reactRoot;

onMounted(async () => {
  const [{ createElement }, { createRoot }, { default: WorkspaceApp }] = await Promise.all([
    import('react'),
    import('react-dom/client'),
    import('./App.jsx'),
  ]);

  reactRoot = createRoot(legacyWorkspace.value);
  reactRoot.render(createElement(WorkspaceApp));
});

onBeforeUnmount(() => reactRoot?.unmount());
</script>

<template>
  <main class="vue-application" aria-label="智能 BI 数据洞察与报告生成平台">
    <div ref="legacyWorkspace" />
  </main>
</template>
