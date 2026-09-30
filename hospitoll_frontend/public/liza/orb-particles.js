(() => {
  const canvas = document.getElementById('canvasOne')
  const context = canvas?.getContext('2d')
  if (!canvas || !context) return

  const particleCount = 300
  const goldenAngle = Math.PI * (3 - Math.sqrt(5))
  const particles = Array.from({ length: particleCount }, (_, index) => {
    const y = 1 - (index / (particleCount - 1)) * 2
    const ringRadius = Math.sqrt(1 - y * y)
    const angle = goldenAngle * index
    return {
      x: Math.cos(angle) * ringRadius,
      y,
      z: Math.sin(angle) * ringRadius,
      tone: index % 7 === 0 ? 'mint' : 'blue',
    }
  })
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  let width = 0
  let height = 0
  let pixelRatio = 1
  let rotation = 0
  let frameId = 0

  const resize = () => {
    const bounds = canvas.getBoundingClientRect()
    if (!bounds.width || !bounds.height) return
    width = bounds.width
    height = bounds.height
    pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = Math.round(width * pixelRatio)
    canvas.height = Math.round(height * pixelRatio)
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
    draw()
  }

  const draw = () => {
    if (!width || !height) return
    context.clearRect(0, 0, width, height)
    const radius = Math.min(width, height) * 0.4
    const yaw = rotation
    const pitch = -0.12
    const cosYaw = Math.cos(yaw)
    const sinYaw = Math.sin(yaw)
    const cosPitch = Math.cos(pitch)
    const sinPitch = Math.sin(pitch)
    const focalLength = 2.8

    particles.forEach((particle) => {
      const rotatedX = particle.x * cosYaw + particle.z * sinYaw
      const rotatedZ = particle.z * cosYaw - particle.x * sinYaw
      const rotatedY = particle.y * cosPitch - rotatedZ * sinPitch
      const depth = particle.y * sinPitch + rotatedZ * cosPitch
      const perspective = focalLength / (focalLength - depth * 0.48)
      const x = width / 2 + rotatedX * radius * perspective
      const y = height / 2 + rotatedY * radius * perspective
      const frontness = (depth + 1) / 2
      const dotRadius = 0.65 + frontness * 0.85
      const alpha = 0.13 + frontness * 0.7
      context.beginPath()
      context.fillStyle = particle.tone === 'mint'
        ? `rgba(124, 235, 211, ${alpha * 0.8})`
        : `rgba(54, 126, 255, ${alpha})`
      context.shadowBlur = frontness > 0.68 ? 5 : 0
      context.shadowColor = particle.tone === 'mint' ? '#67e3c2' : '#287bff'
      context.arc(x, y, dotRadius, 0, Math.PI * 2)
      context.fill()
    })
    context.shadowBlur = 0
  }

  const animate = () => {
    draw()
    if (!reduceMotion && document.visibilityState === 'visible') {
      rotation += 0.004
      frameId = window.requestAnimationFrame(animate)
    }
  }

  const start = () => {
    window.cancelAnimationFrame(frameId)
    frameId = window.requestAnimationFrame(animate)
  }

  if ('ResizeObserver' in window) new ResizeObserver(resize).observe(canvas)
  else window.addEventListener('resize', resize)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') start()
    else window.cancelAnimationFrame(frameId)
  })
  resize()
  start()
})()
