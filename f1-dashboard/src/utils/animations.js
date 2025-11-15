import anime from 'animejs';

/**
 * F1 Racing-Inspired Animation Utilities
 * Collection of animejs-based animations for the F1 dashboard
 */

/**
 * Speed line animation - creates racing stripe effect
 */
export const speedLines = (element, options = {}) => {
  const {
    duration = 2000,
    direction = 'horizontal',
    intensity = 1,
    color = '#E10600'
  } = options;

  if (!element) return;

  // Create speed line elements
  const lines = [];
  const count = Math.floor(5 * intensity);
  
  for (let i = 0; i < count; i++) {
    const line = document.createElement('div');
    line.style.position = 'absolute';
    line.style.width = direction === 'horizontal' ? '100%' : '2px';
    line.style.height = direction === 'horizontal' ? '2px' : '100%';
    line.style.background = `linear-gradient(${direction === 'horizontal' ? '90deg' : '0deg'}, transparent, ${color}, transparent)`;
    line.style.opacity = '0';
    line.style.pointerEvents = 'none';
    element.style.position = 'relative';
    element.appendChild(line);
    lines.push(line);
  }

  const animation = anime({
    targets: lines,
    opacity: [
      { value: 0, duration: 0 },
      { value: 0.8, duration: duration * 0.2 },
      { value: 0.8, duration: duration * 0.6 },
      { value: 0, duration: duration * 0.2 }
    ],
    translateX: direction === 'horizontal' 
      ? anime.stagger([-50, 50], { from: 'center' })
      : 0,
    translateY: direction === 'vertical'
      ? anime.stagger([-50, 50], { from: 'center' })
      : 0,
    duration: duration,
    easing: 'easeInOutQuad',
    complete: () => {
      lines.forEach(line => line.remove());
    }
  });

  return animation;
};

/**
 * Checkered flag pattern animation
 */
export const checkeredFlag = (element, options = {}) => {
  const {
    duration = 1000,
    size = 20,
    colors = ['#FFFFFF', '#000000'],
    lapNumber = null
  } = options;

  if (!element) return;

  const pattern = document.createElement('div');
  pattern.className = 'checkered-flag-pattern';
  pattern.style.position = 'absolute';
  pattern.style.top = '0';
  pattern.style.left = '0';
  pattern.style.width = '100%';
  pattern.style.height = '100%';
  pattern.style.backgroundImage = `
    repeating-linear-gradient(
      45deg,
      ${colors[0]} 0px,
      ${colors[0]} ${size}px,
      ${colors[1]} ${size}px,
      ${colors[1]} ${size * 2}px
    )
  `;
  pattern.style.opacity = '0';
  pattern.style.pointerEvents = 'none';
  element.style.position = 'relative';
  element.appendChild(pattern);

  // Add lap number text overlay if provided
  let lapText = null;
  if (lapNumber !== null && lapNumber !== undefined) {
    lapText = document.createElement('div');
    lapText.className = 'checkered-flag-lap-text';
    lapText.textContent = `LAP ${lapNumber}`;
    lapText.style.position = 'absolute';
    lapText.style.top = '50%';
    lapText.style.left = '50%';
    lapText.style.transform = 'translate(-50%, -50%)';
    lapText.style.fontSize = '32px';
    lapText.style.fontWeight = '900';
    lapText.style.color = '#FFFFFF';
    lapText.style.textShadow = '2px 2px 4px rgba(0, 0, 0, 0.8), 0 0 10px rgba(225, 6, 0, 0.8)';
    lapText.style.zIndex = '21';
    lapText.style.pointerEvents = 'none';
    lapText.style.opacity = '0';
    lapText.style.fontFamily = 'F1-Bold, sans-serif';
    lapText.style.letterSpacing = '2px';
    element.appendChild(lapText);
  }

  const animation = anime({
    targets: pattern,
    opacity: [0, 1, 1, 0],
    scale: [0.8, 1, 1, 1.2],
    duration: duration,
    easing: 'easeInOutQuad',
    complete: () => {
      pattern.remove();
      if (lapText) lapText.remove();
    }
  });

  // Animate lap text separately
  if (lapText) {
    anime({
      targets: lapText,
      opacity: [0, 1, 1, 0],
      scale: [0.5, 1.1, 1, 1.2],
      duration: duration,
      easing: 'easeInOutQuad'
    });
  }

  return animation;
};

/**
 * Pit stop countdown animation
 */
export const pitStopCountdown = (element, seconds, onComplete) => {
  if (!element) return;

  const countdown = document.createElement('div');
  countdown.className = 'pit-countdown';
  countdown.style.position = 'absolute';
  countdown.style.top = '50%';
  countdown.style.left = '50%';
  countdown.style.transform = 'translate(-50%, -50%)';
  countdown.style.fontSize = '48px';
  countdown.style.fontWeight = 'bold';
  countdown.style.color = '#E10600';
  countdown.style.textShadow = '0 0 20px rgba(225, 6, 0, 0.8)';
  countdown.style.zIndex = '1000';
  element.style.position = 'relative';
  element.appendChild(countdown);

  let current = seconds;
  countdown.textContent = current;

  const interval = setInterval(() => {
    current--;
    if (current > 0) {
      anime({
        targets: countdown,
        scale: [1, 1.5, 1],
        opacity: [1, 0.5, 1],
        duration: 500,
        easing: 'easeInOutQuad'
      });
      countdown.textContent = current;
    } else {
      clearInterval(interval);
      anime({
        targets: countdown,
        scale: [1, 2],
        opacity: [1, 0],
        duration: 500,
        easing: 'easeInOutQuad',
        complete: () => {
          countdown.remove();
          if (onComplete) onComplete();
        }
      });
    }
  }, 1000);

  return { interval, countdown };
};

/**
 * Telemetry data flow animation
 */
export const telemetryFlow = (element, options = {}) => {
  const {
    duration = 2000,
    color = '#4a90e2',
    direction = 'right'
  } = options;

  if (!element) return;

  const flow = document.createElement('div');
  flow.style.position = 'absolute';
  flow.style.top = '0';
  flow.style.left = direction === 'right' ? '-100%' : '100%';
  flow.style.width = '30%';
  flow.style.height = '100%';
  flow.style.background = `linear-gradient(${direction === 'right' ? '90deg' : '270deg'}, transparent, ${color}40, transparent)`;
  flow.style.pointerEvents = 'none';
  element.style.position = 'relative';
  element.style.overflow = 'hidden';
  element.appendChild(flow);

  return anime({
    targets: flow,
    left: direction === 'right' ? '100%' : '-100%',
    duration: duration,
    easing: 'linear',
    loop: true
  });
};

/**
 * Position change animation with motion blur effect
 */
export const positionChange = (element, direction, options = {}) => {
  const {
    duration = 600,
    intensity = 1
  } = options;

  if (!element) return;

  const isUp = direction === 'up' || direction > 0;
  const translateY = isUp ? -30 * intensity : 30 * intensity;

  return anime({
    targets: element,
    translateY: [0, translateY * 0.7, 0],
    opacity: [1, 0.9, 1],
    scale: [1, 1.02, 1],
    duration: duration,
    easing: 'easeOutCubic',
    filter: [
      { value: 'blur(0px)', duration: 0 },
      { value: `blur(${2 * intensity}px)`, duration: duration * 0.15 },
      { value: 'blur(0px)', duration: duration * 0.85 }
    ]
  });
};

/**
 * DRS activation pulse animation
 */
export const drsPulse = (element, options = {}) => {
  const {
    duration = 1000,
    color = '#00ff00',
    intensity = 1
  } = options;

  if (!element) return;

  return anime({
    targets: element,
    scale: [1, 1.3 * intensity, 1],
    boxShadow: [
      `0 0 0px ${color}`,
      `0 0 ${20 * intensity}px ${color}`,
      `0 0 0px ${color}`
    ],
    duration: duration,
    easing: 'easeInOutQuad',
    loop: true
  });
};

/**
 * Lap counter flip animation
 */
export const lapCounterFlip = (element, newValue, options = {}) => {
  const {
    duration = 500
  } = options;

  if (!element) return;

  return anime({
    targets: element,
    rotateX: [0, 90, 0],
    duration: duration,
    easing: 'easeInOutQuad',
    begin: () => {
      element.style.transformOrigin = 'center';
    },
    update: (anim) => {
      if (anim.progress > 50 && anim.progress < 51) {
        element.textContent = newValue;
      }
    }
  });
};

/**
 * Start/finish line flash animation
 */
export const finishLineFlash = (element, options = {}) => {
  const {
    duration = 300,
    color = '#FFFFFF'
  } = options;

  if (!element) return;

  return anime({
    targets: element,
    backgroundColor: [
      { value: 'transparent', duration: 0 },
      { value: color, duration: duration * 0.3 },
      { value: 'transparent', duration: duration * 0.7 }
    ],
    opacity: [0, 1, 0],
    duration: duration,
    easing: 'easeInOutQuad'
  });
};

/**
 * Racing spotlight effect for selected car
 */
export const racingSpotlight = (element, options = {}) => {
  const {
    duration = 2000,
    color = '#FFD700'
  } = options;

  if (!element) return;

  const spotlight = document.createElement('div');
  spotlight.style.position = 'absolute';
  spotlight.style.top = '50%';
  spotlight.style.left = '50%';
  spotlight.style.width = '200%';
  spotlight.style.height = '200%';
  spotlight.style.background = `radial-gradient(circle, ${color}20 0%, transparent 70%)`;
  spotlight.style.transform = 'translate(-50%, -50%)';
  spotlight.style.pointerEvents = 'none';
  spotlight.style.zIndex = '-1';
  element.style.position = 'relative';
  element.appendChild(spotlight);

  return anime({
    targets: spotlight,
    opacity: [0, 0.6, 0.6, 0],
    scale: [0.5, 1, 1, 1.5],
    duration: duration,
    easing: 'easeInOutQuad',
    loop: true
  });
};

/**
 * Tire mark skid animation
 */
export const tireMarks = (element, options = {}) => {
  const {
    duration = 1000,
    intensity = 1,
    color = '#333333'
  } = options;

  if (!element) return;

  const marks = [];
  const count = Math.floor(3 * intensity);

  for (let i = 0; i < count; i++) {
    const mark = document.createElement('div');
    mark.style.position = 'absolute';
    mark.style.width = '4px';
    mark.style.height = `${20 + i * 10}px`;
    mark.style.background = color;
    mark.style.opacity = '0.6';
    mark.style.borderRadius = '2px';
    mark.style.pointerEvents = 'none';
    mark.style.transform = `rotate(${i * 15}deg)`;
    element.style.position = 'relative';
    element.appendChild(mark);
    marks.push(mark);
  }

  return anime({
    targets: marks,
    opacity: [0.6, 0.3, 0],
    translateX: anime.stagger(10),
    translateY: anime.stagger(5),
    rotate: anime.stagger(15),
    duration: duration,
    easing: 'easeOutQuad',
    complete: () => {
      marks.forEach(mark => mark.remove());
    }
  });
};

/**
 * Speedometer sweep animation
 */
export const speedometerSweep = (element, targetValue, options = {}) => {
  const {
    duration = 1000,
    min = 0,
    max = 350
  } = options;

  if (!element) return;

  const startValue = parseFloat(element.textContent) || min;
  const value = Math.min(Math.max(targetValue, min), max);

  return anime({
    targets: { value: startValue },
    value: value,
    duration: duration,
    easing: 'easeOutCubic',
    update: (anim) => {
      element.textContent = Math.round(anim.animatables[0].target.value);
    }
  });
};

/**
 * Gear shift animation with RPM rev
 */
export const gearShift = (element, newGear, options = {}) => {
  const {
    duration = 400
  } = options;

  if (!element) return;

  return anime({
    targets: element,
    scale: [1, 1.5, 1],
    rotateZ: [0, 360, 0],
    color: ['#FFFFFF', '#FFD700', '#FFFFFF'],
    duration: duration,
    easing: 'easeOutElastic(1, .6)',
    begin: () => {
      element.textContent = newGear;
    }
  });
};

/**
 * Page load checkered flag reveal
 */
export const pageLoadReveal = (element, options = {}) => {
  const {
    duration = 1500
  } = options;

  if (!element) return;

  return anime({
    targets: element,
    opacity: [0, 1],
    translateY: [30, 0],
    duration: duration,
    easing: 'easeOutCubic',
    delay: anime.stagger(100, { from: 'first' })
  });
};

/**
 * Connection pulse animation
 */
export const connectionPulse = (element, isConnected, options = {}) => {
  const {
    duration = 2000,
    connectedColor = '#00ff00',
    disconnectedColor = '#ff0000'
  } = options;

  if (!element) return;

  const color = isConnected ? connectedColor : disconnectedColor;

  return anime({
    targets: element,
    scale: [1, 1.2, 1],
    boxShadow: [
      `0 0 0px ${color}`,
      `0 0 ${15}px ${color}`,
      `0 0 0px ${color}`
    ],
    duration: duration,
    easing: 'easeInOutQuad',
    loop: true
  });
};

/**
 * Overtaking badge animation
 */
export const overtakingBadge = (element, options = {}) => {
  const {
    duration = 800
  } = options;

  if (!element) return;

  return anime({
    targets: element,
    scale: [0, 1.3, 1],
    rotateZ: [0, 360],
    opacity: [0, 1],
    duration: duration,
    easing: 'easeOutElastic(1, .8)'
  });
};

/**
 * Animated counter with flip effect
 */
export const animatedCounter = (element, targetValue, options = {}) => {
  const {
    duration = 1000,
    decimals = 0
  } = options;

  if (!element) return;

  const startValue = parseFloat(element.textContent) || 0;

  return anime({
    targets: { value: startValue },
    value: targetValue,
    duration: duration,
    easing: 'easeOutCubic',
    update: (anim) => {
      const value = anim.animatables[0].target.value;
      element.textContent = decimals > 0 ? value.toFixed(decimals) : Math.round(value);
    }
  });
};

/**
 * Speed streak trail effect
 */
export const speedStreak = (element, options = {}) => {
  const {
    duration = 500,
    color = '#E10600',
    intensity = 1
  } = options;

  if (!element) return;

  const streak = document.createElement('div');
  streak.style.position = 'absolute';
  streak.style.top = '0';
  streak.style.left = '0';
  streak.style.width = '100%';
  streak.style.height = '100%';
  streak.style.background = `linear-gradient(90deg, transparent, ${color}80, transparent)`;
  streak.style.opacity = '0';
  streak.style.pointerEvents = 'none';
  streak.style.filter = 'blur(2px)';
  element.style.position = 'relative';
  element.appendChild(streak);

  return anime({
    targets: streak,
    opacity: [0, 0.8 * intensity, 0],
    translateX: ['-100%', '100%'],
    duration: duration,
    easing: 'easeInOutQuad',
    complete: () => {
      streak.remove();
    }
  });
};

