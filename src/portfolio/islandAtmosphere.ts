import * as THREE from 'three';

export type IslandLighting='twilight'|'midnight'|'dawn';
export const ISLAND_LIGHTING={
 twilight:{sky:'#11172e',fog:'#18203c',key:'#ffdfce',rim:'#90acff',accent:'#73e3ee',exposure:1.08},
 midnight:{sky:'#070e20',fog:'#111b34',key:'#b8cced',rim:'#8d83f5',accent:'#87bbff',exposure:.95},
 dawn:{sky:'#28354c',fog:'#3b455b',key:'#ffd6ab',rim:'#9dc6e6',accent:'#f3c1b7',exposure:1.12}
} as const;

/** Atmosphere is deliberately separate from the framed island geometry. */
export function createIslandAtmosphere(lite=false){
 const root=new THREE.Group();root.name='island-atmosphere';root.userData.excludeFromIslandFraming=true;
 const materials:THREE.Material[]=[];
 const nebula=new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,
  uniforms:{uTime:{value:0},uColor:{value:new THREE.Color('#566dc0')},uStrength:{value:lite?.08:.16}},
  vertexShader:'varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
  fragmentShader:`varying vec2 vUv; uniform float uTime;uniform vec3 uColor;uniform float uStrength;
   void main(){vec2 p=vUv*2.0-1.0;float wave=sin(p.x*3.4+uTime*.025)*.15+sin(p.x*6.0-uTime*.019)*.045;
    float ribbon=exp(-pow((p.y-wave)*4.2,2.0));float fade=pow(max(0.0,1.0-abs(p.x)),1.4)*(1.0-smoothstep(.2,1.0,abs(p.y)));
    gl_FragColor=vec4(uColor,ribbon*fade*uStrength);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
   }`
 });materials.push(nebula);
 const curtain=new THREE.Mesh(new THREE.PlaneGeometry(58,27),nebula);curtain.position.set(0,4,-23);root.add(curtain);
 const count=lite?36:100,positions=new Float32Array(count*3),phases=new Float32Array(count);
 for(let n=0;n<count;n++){const a=n*2.399963,r=9+(n%9)*1.25;positions.set([Math.cos(a)*r,-2+(n%13)*.8,Math.sin(a)*r-2],n*3);phases[n]=(n*.618)%1;}
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));geometry.setAttribute('phase',new THREE.BufferAttribute(phases,1));
 const motes=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
  uniforms:{uTime:{value:0},uColor:{value:new THREE.Color('#b8ccf5')},uSize:{value:lite?18:28}},
  vertexShader:'attribute float phase;uniform float uTime;uniform float uSize;varying float vAlpha;void main(){vec3 p=position;p.y+=sin(uTime*.13+phase*6.283)*.18;vec4 mv=modelViewMatrix*vec4(p,1.0);gl_Position=projectionMatrix*mv;gl_PointSize=clamp(uSize*(.6+phase)/max(1.0,-mv.z),1.0,4.0);vAlpha=.18+phase*.38;}',
  fragmentShader:`uniform vec3 uColor;varying float vAlpha;
   void main(){float d=length(gl_PointCoord-.5)*2.0;float alpha=pow(max(0.0,1.0-d),2.0)*vAlpha;
    gl_FragColor=vec4(uColor,alpha);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
   }`
 });materials.push(motes);root.add(new THREE.Points(geometry,motes));
 return {root,materials,update(time:number){nebula.uniforms.uTime.value=time;motes.uniforms.uTime.value=time;},lighting(mode:IslandLighting){nebula.uniforms.uColor.value.set(mode==='dawn'?'#c18caa':mode==='midnight'?'#435e9e':'#566dc0');motes.uniforms.uColor.value.set(ISLAND_LIGHTING[mode].accent);}};
}
