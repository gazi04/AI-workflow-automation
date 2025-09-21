<template>
  <div>
    <h1>Connect Your Apps</h1>
    <div class="connection-card">
      <h2>Google</h2>
      <p>Connect your Gmail to send and receive emails.</p>
      <button @click="connectGoogle" :disabled="isConnecting">Connect Gmail</button>
    </div>
    <div class="connection-card">
      <h2>Slack</h2>
      <p>Connect Slack to send messages.</p>
      <button @click="connectSlack" :disabled="isConnecting">Connect Slack</button>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue';
import { useRouter } from 'vue-router';

export default {
  setup() {
    const isConnecting = ref(false);
    const router = useRouter();

    const connectGoogle = async () => {
      isConnecting.value = true;
      try {
        const response = await fetch('http://localhost:8000/api/auth/connect/google');
        const data = await response.json();
        // Redirect the user to Google's login page
        window.location.href = data.auth_url;
      } catch (error) {
        console.error('Connection failed:', error);
      } finally {
        isConnecting.value = false;
      }
    };

    const connectSlack = async () => {
      // Similar logic for Slack
      // You would call /api/auth/connect/slack
    };

    return { connectGoogle, connectSlack, isConnecting };
  }
};
</script>
