import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export const ParticleBackground: React.FC = () => {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Check reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Responsive particle count
    const isMobile = window.innerWidth < 768;
    const particleCount = isMobile ? 350 : 900;

    // Scene setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      60,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.z = 30;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Buffers for 3 states: Scattered (0), Waveform (1), Grid (2)
    const positions = new Float32Array(particleCount * 3);
    const scattered = new Float32Array(particleCount * 3);
    const waveform = new Float32Array(particleCount * 3);
    const grid = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    const baseColor = new THREE.Color('#4f46e5'); // Indigo
    const softColor = new THREE.Color('#94a3b8'); // Soft Slate

    const gridSize = Math.ceil(Math.sqrt(particleCount));
    const spacing = 1.2;

    for (let i = 0; i < particleCount; i++) {
      const i3 = i * 3;

      // 1. Scattered state
      scattered[i3] = (Math.random() - 0.5) * 50;
      scattered[i3 + 1] = (Math.random() - 0.5) * 35;
      scattered[i3 + 2] = (Math.random() - 0.5) * 25;

      // 2. Waveform state
      const t = (i / particleCount) * Math.PI * 4;
      waveform[i3] = (i / particleCount - 0.5) * 40;
      waveform[i3 + 1] = Math.sin(t) * 5 * Math.sin(i * 0.1);
      waveform[i3 + 2] = (Math.random() - 0.5) * 6;

      // 3. Grid state
      const row = Math.floor(i / gridSize);
      const col = i % gridSize;
      grid[i3] = (col - gridSize / 2) * spacing;
      grid[i3 + 1] = (row - gridSize / 2) * spacing;
      grid[i3 + 2] = 0;

      // Start at scattered
      positions[i3] = scattered[i3];
      positions[i3 + 1] = scattered[i3 + 1];
      positions[i3 + 2] = scattered[i3 + 2];

      // Blend subtle indigo and soft slate colors
      const mixRatio = Math.random();
      const c = baseColor.clone().lerp(softColor, mixRatio);
      colors[i3] = c.r;
      colors[i3 + 1] = c.g;
      colors[i3 + 2] = c.b;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Particle Material
    const material = new THREE.PointsMaterial({
      size: isMobile ? 0.35 : 0.45,
      vertexColors: true,
      transparent: true,
      opacity: 0.65,
      blending: THREE.NormalBlending,
    });

    const pointCloud = new THREE.Points(geometry, material);
    scene.add(pointCloud);

    // Scroll state tracking
    let scrollRatio = 0;
    const handleScroll = () => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      if (maxScroll > 0) {
        scrollRatio = Math.min(Math.max(window.scrollY / maxScroll, 0), 1);
      }
    };
    window.addEventListener('scroll', handleScroll, { passive: true });

    let animationFrameId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      if (!prefersReducedMotion) {
        const posAttr = geometry.attributes.position as THREE.BufferAttribute;
        const currentArr = posAttr.array as Float32Array;

        // Determine morph target based on scroll:
        // 0.0 - 0.35: Scattered -> Waveform
        // 0.35 - 1.0: Waveform -> Grid
        let targetArr1: Float32Array;
        let targetArr2: Float32Array;
        let factor: number;

        if (scrollRatio < 0.4) {
          targetArr1 = scattered;
          targetArr2 = waveform;
          factor = scrollRatio / 0.4;
        } else {
          targetArr1 = waveform;
          targetArr2 = grid;
          factor = (scrollRatio - 0.4) / 0.6;
        }

        for (let i = 0; i < particleCount; i++) {
          const i3 = i * 3;
          // Interpolate between targets
          const tx = targetArr1[i3] * (1 - factor) + targetArr2[i3] * factor;
          let ty = targetArr1[i3 + 1] * (1 - factor) + targetArr2[i3 + 1] * factor;
          const tz = targetArr1[i3 + 2] * (1 - factor) + targetArr2[i3 + 2] * factor;

          // Gentle ambient wave breathing
          ty += Math.sin(elapsedTime * 1.5 + i * 0.05) * 0.25;

          // Smooth lerp towards target position
          currentArr[i3] += (tx - currentArr[i3]) * 0.08;
          currentArr[i3 + 1] += (ty - currentArr[i3 + 1]) * 0.08;
          currentArr[i3 + 2] += (tz - currentArr[i3 + 2]) * 0.08;
        }

        posAttr.needsUpdate = true;
        pointCloud.rotation.y = elapsedTime * 0.04;
      }

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      geometry.dispose();
      material.dispose();
      renderer.dispose();
    };
  }, []);

  return (
    <div
      ref={mountRef}
      className="fixed inset-0 pointer-events-none z-0 overflow-hidden opacity-40"
      aria-hidden="true"
    />
  );
};
