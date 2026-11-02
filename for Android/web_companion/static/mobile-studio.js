(()=>{var Bf=Object.defineProperty;var kf=(i,t,e)=>t in i?Bf(i,t,{enumerable:!0,configurable:!0,writable:!0,value:e}):i[t]=e;var ae=(i,t,e)=>kf(i,typeof t!="symbol"?t+"":t,e);/**
 * @license
 * Copyright 2010-2026 Three.js Authors
 * SPDX-License-Identifier: MIT
 */var _s={LEFT:0,MIDDLE:1,RIGHT:2,ROTATE:0,DOLLY:1,PAN:2},ys={ROTATE:0,PAN:1,DOLLY_PAN:2,DOLLY_ROTATE:3},Cu=0,kc=1,Pu=2;var Zi=1,Iu=2,Dr=3,vs=0,Tn=1,Ai=2,Ri=0,Nr=1,Hc=2,Vc=3,Gc=4,Lu=5;var Xs=100,zu=101,Du=102,Nu=103,Uu=104,Fu=200,Ou=201,Bu=202,ku=203,Wc=204,Xc=205,Hu=206,Vu=207,Gu=208,Wu=209,Xu=210,qu=211,Yu=212,Zu=213,$u=214,_o=0,yo=1,vo=2,Mr=3,bo=4,Mo=5,So=6,Eo=7,qc=0,Ku=1,Ju=2,ui=0,Yc=1,Zc=2,$c=3,qs=4,Kc=5,Jc=6,jc=7;var Qc=300,bs=301,Ys=302,Zo=303,$o=304,Aa=306,Si=1e3,Mi=1001,wo=1002,an=1003,ju=1004;var Ra=1005;var mn=1006,Ko=1007;var Ms=1008;var Dn=1009,th=1010,eh=1011,Ur=1012,Jo=1013,di=1014,Zn=1015,fi=1016,jo=1017,Qo=1018,Fr=1020,nh=35902,ih=35899,sh=1021,rh=1022,$n=1023,Ei=1026,Ss=1027,tl=1028,el=1029,Es=1030,nl=1031;var il=1033,Ca=33776,Pa=33777,Ia=33778,La=33779,sl=35840,rl=35841,al=35842,ol=35843,ll=36196,cl=37492,hl=37496,ul=37488,dl=37489,za=37490,fl=37491,pl=37808,ml=37809,gl=37810,xl=37811,_l=37812,yl=37813,vl=37814,bl=37815,Ml=37816,Sl=37817,El=37818,wl=37819,Tl=37820,Al=37821,Rl=36492,Cl=36494,Pl=36495,Il=36283,Ll=36284,Da=36285,zl=36286;var ca=2300,To=2301,go=2302,Ic=2303,Lc=2400,zc=2401,Dc=2402;var Qu=3200;var Dl=0,td=1,$i="",Ge="srgb",ha="srgb-linear",ua="linear",Ae="srgb";var xo=7680;var ed=519,nd=512,id=513,sd=514,Nl=515,rd=516,ad=517,Ul=518,od=519,ld=35044;var ah="300 es",li=2e3,Sr=2001;function Hf(i){for(let t=i.length-1;t>=0;--t)if(i[t]>=65535)return!0;return!1}function Vf(i){return ArrayBuffer.isView(i)&&!(i instanceof DataView)}function da(i){return document.createElementNS("http://www.w3.org/1999/xhtml",i)}function cd(){let i=da("canvas");return i.style.display="block",i}var iu={},Er=null;function oh(...i){let t="THREE."+i.shift();Er?Er("log",t,...i):console.log(t,...i)}function hd(i){let t=i[0];if(typeof t=="string"&&t.startsWith("TSL:")){let e=i[1];e&&e.isStackTrace?i[0]+=" "+e.getLocation():i[1]='Stack trace not available. Enable "THREE.Node.captureStackTrace" to capture stack traces.'}return i}function Zt(...i){i=hd(i);let t="THREE."+i.shift();if(Er)Er("warn",t,...i);else{let e=i[0];e&&e.isStackTrace?console.warn(e.getError(t)):console.warn(t,...i)}}function Kt(...i){i=hd(i);let t="THREE."+i.shift();if(Er)Er("error",t,...i);else{let e=i[0];e&&e.isStackTrace?console.error(e.getError(t)):console.error(t,...i)}}function Os(...i){let t=i.join(" ");t in iu||(iu[t]=!0,Zt(...i))}function ud(i,t,e){return new Promise(function(n,s){function r(){switch(i.clientWaitSync(t,i.SYNC_FLUSH_COMMANDS_BIT,0)){case i.WAIT_FAILED:s();break;case i.TIMEOUT_EXPIRED:setTimeout(r,e);break;default:n()}}setTimeout(r,e)})}var dd={[_o]:yo,[vo]:So,[bo]:Eo,[Mr]:Mo,[yo]:_o,[So]:vo,[Eo]:bo,[Mo]:Mr},ci=class{addEventListener(t,e){this._listeners===void 0&&(this._listeners={});let n=this._listeners;n[t]===void 0&&(n[t]=[]),n[t].indexOf(e)===-1&&n[t].push(e)}hasEventListener(t,e){let n=this._listeners;return n===void 0?!1:n[t]!==void 0&&n[t].indexOf(e)!==-1}removeEventListener(t,e){let n=this._listeners;if(n===void 0)return;let s=n[t];if(s!==void 0){let r=s.indexOf(e);r!==-1&&s.splice(r,1)}}dispatchEvent(t){let e=this._listeners;if(e===void 0)return;let n=e[t.type];if(n!==void 0){t.target=this;let s=n.slice(0);for(let r=0,a=s.length;r<a;r++)s[r].call(this,t);t.target=null}}},xn=["00","01","02","03","04","05","06","07","08","09","0a","0b","0c","0d","0e","0f","10","11","12","13","14","15","16","17","18","19","1a","1b","1c","1d","1e","1f","20","21","22","23","24","25","26","27","28","29","2a","2b","2c","2d","2e","2f","30","31","32","33","34","35","36","37","38","39","3a","3b","3c","3d","3e","3f","40","41","42","43","44","45","46","47","48","49","4a","4b","4c","4d","4e","4f","50","51","52","53","54","55","56","57","58","59","5a","5b","5c","5d","5e","5f","60","61","62","63","64","65","66","67","68","69","6a","6b","6c","6d","6e","6f","70","71","72","73","74","75","76","77","78","79","7a","7b","7c","7d","7e","7f","80","81","82","83","84","85","86","87","88","89","8a","8b","8c","8d","8e","8f","90","91","92","93","94","95","96","97","98","99","9a","9b","9c","9d","9e","9f","a0","a1","a2","a3","a4","a5","a6","a7","a8","a9","aa","ab","ac","ad","ae","af","b0","b1","b2","b3","b4","b5","b6","b7","b8","b9","ba","bb","bc","bd","be","bf","c0","c1","c2","c3","c4","c5","c6","c7","c8","c9","ca","cb","cc","cd","ce","cf","d0","d1","d2","d3","d4","d5","d6","d7","d8","d9","da","db","dc","dd","de","df","e0","e1","e2","e3","e4","e5","e6","e7","e8","e9","ea","eb","ec","ed","ee","ef","f0","f1","f2","f3","f4","f5","f6","f7","f8","f9","fa","fb","fc","fd","fe","ff"],su=1234567,oa=Math.PI/180,wr=180/Math.PI;function Or(){let i=Math.random()*4294967295|0,t=Math.random()*4294967295|0,e=Math.random()*4294967295|0,n=Math.random()*4294967295|0;return(xn[i&255]+xn[i>>8&255]+xn[i>>16&255]+xn[i>>24&255]+"-"+xn[t&255]+xn[t>>8&255]+"-"+xn[t>>16&15|64]+xn[t>>24&255]+"-"+xn[e&63|128]+xn[e>>8&255]+"-"+xn[e>>16&255]+xn[e>>24&255]+xn[n&255]+xn[n>>8&255]+xn[n>>16&255]+xn[n>>24&255]).toLowerCase()}function de(i,t,e){return Math.max(t,Math.min(e,i))}function lh(i,t){return(i%t+t)%t}function Gf(i,t,e,n,s){return n+(i-t)*(s-n)/(e-t)}function Wf(i,t,e){return i!==t?(e-i)/(t-i):0}function la(i,t,e){return(1-e)*i+e*t}function Xf(i,t,e,n){return la(i,t,1-Math.exp(-e*n))}function qf(i,t=1){return t-Math.abs(lh(i,t*2)-t)}function Yf(i,t,e){return i<=t?0:i>=e?1:(i=(i-t)/(e-t),i*i*(3-2*i))}function Zf(i,t,e){return i<=t?0:i>=e?1:(i=(i-t)/(e-t),i*i*i*(i*(i*6-15)+10))}function $f(i,t){return i+Math.floor(Math.random()*(t-i+1))}function Kf(i,t){return i+Math.random()*(t-i)}function Jf(i){return i*(.5-Math.random())}function jf(i){i!==void 0&&(su=i);let t=su+=1831565813;return t=Math.imul(t^t>>>15,t|1),t^=t+Math.imul(t^t>>>7,t|61),((t^t>>>14)>>>0)/4294967296}function Qf(i){return i*oa}function tp(i){return i*wr}function ep(i){return i>0&&Number.isInteger(i)&&2**Math.round(Math.log2(i))===i}function np(i){return Math.pow(2,Math.ceil(Math.log(i)/Math.LN2))}function ip(i){return Math.pow(2,Math.floor(Math.log(i)/Math.LN2))}function sp(i,t,e,n,s){let r=Math.cos,a=Math.sin,l=r(e/2),o=a(e/2),c=r((t+n)/2),h=a((t+n)/2),f=r((t-n)/2),d=a((t-n)/2),p=r((n-t)/2),x=a((n-t)/2);switch(s){case"XYX":i.set(l*h,o*f,o*d,l*c);break;case"YZY":i.set(o*d,l*h,o*f,l*c);break;case"ZXZ":i.set(o*f,o*d,l*h,l*c);break;case"XZX":i.set(l*h,o*x,o*p,l*c);break;case"YXY":i.set(o*p,l*h,o*x,l*c);break;case"ZYZ":i.set(o*x,o*p,l*h,l*c);break;default:Zt("MathUtils: .setQuaternionFromProperEuler() encountered an unknown order: "+s)}}function vr(i,t){switch(t.constructor){case Float32Array:return i;case Uint32Array:return i/4294967295;case Uint16Array:return i/65535;case Uint8Array:case Uint8ClampedArray:return i/255;case Int32Array:return Math.max(i/2147483647,-1);case Int16Array:return Math.max(i/32767,-1);case Int8Array:return Math.max(i/127,-1);default:throw new Error("THREE.MathUtils: Invalid component type.")}}function En(i,t){switch(t.constructor){case Float32Array:return i;case Uint32Array:return Math.round(i*4294967295);case Uint16Array:return Math.round(i*65535);case Uint8Array:case Uint8ClampedArray:return Math.round(i*255);case Int32Array:return Math.round(i*2147483647);case Int16Array:return Math.round(i*32767);case Int8Array:return Math.round(i*127);default:throw new Error("THREE.MathUtils: Invalid component type.")}}var ln={DEG2RAD:oa,RAD2DEG:wr,generateUUID:Or,clamp:de,euclideanModulo:lh,mapLinear:Gf,inverseLerp:Wf,lerp:la,damp:Xf,pingpong:qf,smoothstep:Yf,smootherstep:Zf,randInt:$f,randFloat:Kf,randFloatSpread:Jf,seededRandom:jf,degToRad:Qf,radToDeg:tp,isPowerOfTwo:ep,ceilPowerOfTwo:np,floorPowerOfTwo:ip,setQuaternionFromProperEuler:sp,normalize:En,denormalize:vr},fh=class fh{constructor(t=0,e=0){this.x=t,this.y=e}get width(){return this.x}set width(t){this.x=t}get height(){return this.y}set height(t){this.y=t}set(t,e){return this.x=t,this.y=e,this}setScalar(t){return this.x=t,this.y=t,this}setX(t){return this.x=t,this}setY(t){return this.y=t,this}setComponent(t,e){switch(t){case 0:this.x=e;break;case 1:this.y=e;break;default:throw new Error("THREE.Vector2: index is out of range: "+t)}return this}getComponent(t){switch(t){case 0:return this.x;case 1:return this.y;default:throw new Error("THREE.Vector2: index is out of range: "+t)}}clone(){return new this.constructor(this.x,this.y)}copy(t){return this.x=t.x,this.y=t.y,this}add(t){return this.x+=t.x,this.y+=t.y,this}addScalar(t){return this.x+=t,this.y+=t,this}addVectors(t,e){return this.x=t.x+e.x,this.y=t.y+e.y,this}addScaledVector(t,e){return this.x+=t.x*e,this.y+=t.y*e,this}sub(t){return this.x-=t.x,this.y-=t.y,this}subScalar(t){return this.x-=t,this.y-=t,this}subVectors(t,e){return this.x=t.x-e.x,this.y=t.y-e.y,this}multiply(t){return this.x*=t.x,this.y*=t.y,this}multiplyScalar(t){return this.x*=t,this.y*=t,this}divide(t){return this.x/=t.x,this.y/=t.y,this}divideScalar(t){return this.multiplyScalar(1/t)}applyMatrix3(t){let e=this.x,n=this.y,s=t.elements;return this.x=s[0]*e+s[3]*n+s[6],this.y=s[1]*e+s[4]*n+s[7],this}min(t){return this.x=Math.min(this.x,t.x),this.y=Math.min(this.y,t.y),this}max(t){return this.x=Math.max(this.x,t.x),this.y=Math.max(this.y,t.y),this}clamp(t,e){return this.x=de(this.x,t.x,e.x),this.y=de(this.y,t.y,e.y),this}clampScalar(t,e){return this.x=de(this.x,t,e),this.y=de(this.y,t,e),this}clampLength(t,e){let n=this.length();return this.divideScalar(n||1).multiplyScalar(de(n,t,e))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this}negate(){return this.x=-this.x,this.y=-this.y,this}dot(t){return this.x*t.x+this.y*t.y}cross(t){return this.x*t.y-this.y*t.x}lengthSq(){return this.x*this.x+this.y*this.y}length(){return Math.sqrt(this.x*this.x+this.y*this.y)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)}normalize(){return this.divideScalar(this.length()||1)}angle(){return Math.atan2(-this.y,-this.x)+Math.PI}angleTo(t){let e=Math.sqrt(this.lengthSq()*t.lengthSq());if(e===0)return Math.PI/2;let n=this.dot(t)/e;return Math.acos(de(n,-1,1))}distanceTo(t){return Math.sqrt(this.distanceToSquared(t))}distanceToSquared(t){let e=this.x-t.x,n=this.y-t.y;return e*e+n*n}manhattanDistanceTo(t){return Math.abs(this.x-t.x)+Math.abs(this.y-t.y)}setLength(t){return this.normalize().multiplyScalar(t)}lerp(t,e){return this.x+=(t.x-this.x)*e,this.y+=(t.y-this.y)*e,this}lerpVectors(t,e,n){return this.x=t.x+(e.x-t.x)*n,this.y=t.y+(e.y-t.y)*n,this}equals(t){return t.x===this.x&&t.y===this.y}fromArray(t,e=0){return this.x=t[e],this.y=t[e+1],this}toArray(t=[],e=0){return t[e]=this.x,t[e+1]=this.y,t}fromBufferAttribute(t,e){return this.x=t.getX(e),this.y=t.getY(e),this}rotateAround(t,e){let n=Math.cos(e),s=Math.sin(e),r=this.x-t.x,a=this.y-t.y;return this.x=r*n-a*s+t.x,this.y=r*s+a*n+t.y,this}random(){return this.x=Math.random(),this.y=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y}};fh.prototype.isVector2=!0;var Xt=fh,Ye=class{constructor(t=0,e=0,n=0,s=1){this.isQuaternion=!0,this._x=t,this._y=e,this._z=n,this._w=s}static slerpFlat(t,e,n,s,r,a,l){let o=n[s+0],c=n[s+1],h=n[s+2],f=n[s+3],d=r[a+0],p=r[a+1],x=r[a+2],M=r[a+3];if(f!==M||o!==d||c!==p||h!==x){let m=o*d+c*p+h*x+f*M;m<0&&(d=-d,p=-p,x=-x,M=-M,m=-m);let u=1-l;if(m<.9995){let b=Math.acos(m),A=Math.sin(b);u=Math.sin(u*b)/A,l=Math.sin(l*b)/A,o=o*u+d*l,c=c*u+p*l,h=h*u+x*l,f=f*u+M*l}else{o=o*u+d*l,c=c*u+p*l,h=h*u+x*l,f=f*u+M*l;let b=1/Math.sqrt(o*o+c*c+h*h+f*f);o*=b,c*=b,h*=b,f*=b}}t[e]=o,t[e+1]=c,t[e+2]=h,t[e+3]=f}static multiplyQuaternionsFlat(t,e,n,s,r,a){let l=n[s],o=n[s+1],c=n[s+2],h=n[s+3],f=r[a],d=r[a+1],p=r[a+2],x=r[a+3];return t[e]=l*x+h*f+o*p-c*d,t[e+1]=o*x+h*d+c*f-l*p,t[e+2]=c*x+h*p+l*d-o*f,t[e+3]=h*x-l*f-o*d-c*p,t}get x(){return this._x}set x(t){this._x=t,this._onChangeCallback()}get y(){return this._y}set y(t){this._y=t,this._onChangeCallback()}get z(){return this._z}set z(t){this._z=t,this._onChangeCallback()}get w(){return this._w}set w(t){this._w=t,this._onChangeCallback()}set(t,e,n,s){return this._x=t,this._y=e,this._z=n,this._w=s,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._w)}copy(t){return this._x=t.x,this._y=t.y,this._z=t.z,this._w=t.w,this._onChangeCallback(),this}setFromEuler(t,e=!0){let n=t._x,s=t._y,r=t._z,a=t._order,l=Math.cos,o=Math.sin,c=l(n/2),h=l(s/2),f=l(r/2),d=o(n/2),p=o(s/2),x=o(r/2);switch(a){case"XYZ":this._x=d*h*f+c*p*x,this._y=c*p*f-d*h*x,this._z=c*h*x+d*p*f,this._w=c*h*f-d*p*x;break;case"YXZ":this._x=d*h*f+c*p*x,this._y=c*p*f-d*h*x,this._z=c*h*x-d*p*f,this._w=c*h*f+d*p*x;break;case"ZXY":this._x=d*h*f-c*p*x,this._y=c*p*f+d*h*x,this._z=c*h*x+d*p*f,this._w=c*h*f-d*p*x;break;case"ZYX":this._x=d*h*f-c*p*x,this._y=c*p*f+d*h*x,this._z=c*h*x-d*p*f,this._w=c*h*f+d*p*x;break;case"YZX":this._x=d*h*f+c*p*x,this._y=c*p*f+d*h*x,this._z=c*h*x-d*p*f,this._w=c*h*f-d*p*x;break;case"XZY":this._x=d*h*f-c*p*x,this._y=c*p*f-d*h*x,this._z=c*h*x+d*p*f,this._w=c*h*f+d*p*x;break;default:Zt("Quaternion: .setFromEuler() encountered an unknown order: "+a)}return e===!0&&this._onChangeCallback(),this}setFromAxisAngle(t,e){let n=e/2,s=Math.sin(n);return this._x=t.x*s,this._y=t.y*s,this._z=t.z*s,this._w=Math.cos(n),this._onChangeCallback(),this}setFromRotationMatrix(t){let e=t.elements,n=e[0],s=e[4],r=e[8],a=e[1],l=e[5],o=e[9],c=e[2],h=e[6],f=e[10],d=n+l+f;if(d>0){let p=.5/Math.sqrt(d+1);this._w=.25/p,this._x=(h-o)*p,this._y=(r-c)*p,this._z=(a-s)*p}else if(n>l&&n>f){let p=2*Math.sqrt(1+n-l-f);this._w=(h-o)/p,this._x=.25*p,this._y=(s+a)/p,this._z=(r+c)/p}else if(l>f){let p=2*Math.sqrt(1+l-n-f);this._w=(r-c)/p,this._x=(s+a)/p,this._y=.25*p,this._z=(o+h)/p}else{let p=2*Math.sqrt(1+f-n-l);this._w=(a-s)/p,this._x=(r+c)/p,this._y=(o+h)/p,this._z=.25*p}return this._onChangeCallback(),this}setFromUnitVectors(t,e){let n=t.dot(e)+1;return n<1e-8?(n=0,Math.abs(t.x)>Math.abs(t.z)?(this._x=-t.y,this._y=t.x,this._z=0,this._w=n):(this._x=0,this._y=-t.z,this._z=t.y,this._w=n)):(this._x=t.y*e.z-t.z*e.y,this._y=t.z*e.x-t.x*e.z,this._z=t.x*e.y-t.y*e.x,this._w=n),this.normalize()}angleTo(t){return 2*Math.acos(Math.abs(de(this.dot(t),-1,1)))}rotateTowards(t,e){let n=this.angleTo(t);if(n===0)return this;let s=Math.min(1,e/n);return this.slerp(t,s),this}identity(){return this.set(0,0,0,1)}invert(){return this.conjugate()}conjugate(){return this._x*=-1,this._y*=-1,this._z*=-1,this._onChangeCallback(),this}dot(t){return this._x*t._x+this._y*t._y+this._z*t._z+this._w*t._w}lengthSq(){return this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w}length(){return Math.sqrt(this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w)}normalize(){let t=this.length();return t===0?(this._x=0,this._y=0,this._z=0,this._w=1):(t=1/t,this._x=this._x*t,this._y=this._y*t,this._z=this._z*t,this._w=this._w*t),this._onChangeCallback(),this}multiply(t){return this.multiplyQuaternions(this,t)}premultiply(t){return this.multiplyQuaternions(t,this)}multiplyQuaternions(t,e){let n=t._x,s=t._y,r=t._z,a=t._w,l=e._x,o=e._y,c=e._z,h=e._w;return this._x=n*h+a*l+s*c-r*o,this._y=s*h+a*o+r*l-n*c,this._z=r*h+a*c+n*o-s*l,this._w=a*h-n*l-s*o-r*c,this._onChangeCallback(),this}slerp(t,e){let n=t._x,s=t._y,r=t._z,a=t._w,l=this.dot(t);l<0&&(n=-n,s=-s,r=-r,a=-a,l=-l);let o=1-e;if(l<.9995){let c=Math.acos(l),h=Math.sin(c);o=Math.sin(o*c)/h,e=Math.sin(e*c)/h,this._x=this._x*o+n*e,this._y=this._y*o+s*e,this._z=this._z*o+r*e,this._w=this._w*o+a*e,this._onChangeCallback()}else this._x=this._x*o+n*e,this._y=this._y*o+s*e,this._z=this._z*o+r*e,this._w=this._w*o+a*e,this.normalize();return this}slerpQuaternions(t,e,n){return this.copy(t).slerp(e,n)}random(){let t=2*Math.PI*Math.random(),e=2*Math.PI*Math.random(),n=Math.random(),s=Math.sqrt(1-n),r=Math.sqrt(n);return this.set(s*Math.sin(t),s*Math.cos(t),r*Math.sin(e),r*Math.cos(e))}equals(t){return t._x===this._x&&t._y===this._y&&t._z===this._z&&t._w===this._w}fromArray(t,e=0){return this._x=t[e],this._y=t[e+1],this._z=t[e+2],this._w=t[e+3],this._onChangeCallback(),this}toArray(t=[],e=0){return t[e]=this._x,t[e+1]=this._y,t[e+2]=this._z,t[e+3]=this._w,t}fromBufferAttribute(t,e){return this._x=t.getX(e),this._y=t.getY(e),this._z=t.getZ(e),this._w=t.getW(e),this._onChangeCallback(),this}toJSON(){return this.toArray()}_onChange(t){return this._onChangeCallback=t,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._w}},ph=class ph{constructor(t=0,e=0,n=0){this.x=t,this.y=e,this.z=n}set(t,e,n){return n===void 0&&(n=this.z),this.x=t,this.y=e,this.z=n,this}setScalar(t){return this.x=t,this.y=t,this.z=t,this}setX(t){return this.x=t,this}setY(t){return this.y=t,this}setZ(t){return this.z=t,this}setComponent(t,e){switch(t){case 0:this.x=e;break;case 1:this.y=e;break;case 2:this.z=e;break;default:throw new Error("THREE.Vector3: index is out of range: "+t)}return this}getComponent(t){switch(t){case 0:return this.x;case 1:return this.y;case 2:return this.z;default:throw new Error("THREE.Vector3: index is out of range: "+t)}}clone(){return new this.constructor(this.x,this.y,this.z)}copy(t){return this.x=t.x,this.y=t.y,this.z=t.z,this}add(t){return this.x+=t.x,this.y+=t.y,this.z+=t.z,this}addScalar(t){return this.x+=t,this.y+=t,this.z+=t,this}addVectors(t,e){return this.x=t.x+e.x,this.y=t.y+e.y,this.z=t.z+e.z,this}addScaledVector(t,e){return this.x+=t.x*e,this.y+=t.y*e,this.z+=t.z*e,this}sub(t){return this.x-=t.x,this.y-=t.y,this.z-=t.z,this}subScalar(t){return this.x-=t,this.y-=t,this.z-=t,this}subVectors(t,e){return this.x=t.x-e.x,this.y=t.y-e.y,this.z=t.z-e.z,this}multiply(t){return this.x*=t.x,this.y*=t.y,this.z*=t.z,this}multiplyScalar(t){return this.x*=t,this.y*=t,this.z*=t,this}multiplyVectors(t,e){return this.x=t.x*e.x,this.y=t.y*e.y,this.z=t.z*e.z,this}applyEuler(t){return this.applyQuaternion(ru.setFromEuler(t))}applyAxisAngle(t,e){return this.applyQuaternion(ru.setFromAxisAngle(t,e))}applyMatrix3(t){let e=this.x,n=this.y,s=this.z,r=t.elements;return this.x=r[0]*e+r[3]*n+r[6]*s,this.y=r[1]*e+r[4]*n+r[7]*s,this.z=r[2]*e+r[5]*n+r[8]*s,this}applyNormalMatrix(t){return this.applyMatrix3(t).normalize()}applyMatrix4(t){let e=this.x,n=this.y,s=this.z,r=t.elements,a=1/(r[3]*e+r[7]*n+r[11]*s+r[15]);return this.x=(r[0]*e+r[4]*n+r[8]*s+r[12])*a,this.y=(r[1]*e+r[5]*n+r[9]*s+r[13])*a,this.z=(r[2]*e+r[6]*n+r[10]*s+r[14])*a,this}applyQuaternion(t){let e=this.x,n=this.y,s=this.z,r=t.x,a=t.y,l=t.z,o=t.w,c=2*(a*s-l*n),h=2*(l*e-r*s),f=2*(r*n-a*e);return this.x=e+o*c+a*f-l*h,this.y=n+o*h+l*c-r*f,this.z=s+o*f+r*h-a*c,this}project(t){return this.applyMatrix4(t.matrixWorldInverse).applyMatrix4(t.projectionMatrix)}unproject(t){return this.applyMatrix4(t.projectionMatrixInverse).applyMatrix4(t.matrixWorld)}transformDirection(t){let e=this.x,n=this.y,s=this.z,r=t.elements;return this.x=r[0]*e+r[4]*n+r[8]*s,this.y=r[1]*e+r[5]*n+r[9]*s,this.z=r[2]*e+r[6]*n+r[10]*s,this.normalize()}divide(t){return this.x/=t.x,this.y/=t.y,this.z/=t.z,this}divideScalar(t){return this.multiplyScalar(1/t)}min(t){return this.x=Math.min(this.x,t.x),this.y=Math.min(this.y,t.y),this.z=Math.min(this.z,t.z),this}max(t){return this.x=Math.max(this.x,t.x),this.y=Math.max(this.y,t.y),this.z=Math.max(this.z,t.z),this}clamp(t,e){return this.x=de(this.x,t.x,e.x),this.y=de(this.y,t.y,e.y),this.z=de(this.z,t.z,e.z),this}clampScalar(t,e){return this.x=de(this.x,t,e),this.y=de(this.y,t,e),this.z=de(this.z,t,e),this}clampLength(t,e){let n=this.length();return this.divideScalar(n||1).multiplyScalar(de(n,t,e))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this}dot(t){return this.x*t.x+this.y*t.y+this.z*t.z}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)}normalize(){return this.divideScalar(this.length()||1)}setLength(t){return this.normalize().multiplyScalar(t)}lerp(t,e){return this.x+=(t.x-this.x)*e,this.y+=(t.y-this.y)*e,this.z+=(t.z-this.z)*e,this}lerpVectors(t,e,n){return this.x=t.x+(e.x-t.x)*n,this.y=t.y+(e.y-t.y)*n,this.z=t.z+(e.z-t.z)*n,this}cross(t){return this.crossVectors(this,t)}crossVectors(t,e){let n=t.x,s=t.y,r=t.z,a=e.x,l=e.y,o=e.z;return this.x=s*o-r*l,this.y=r*a-n*o,this.z=n*l-s*a,this}projectOnVector(t){let e=t.lengthSq();if(e===0)return this.set(0,0,0);let n=t.dot(this)/e;return this.copy(t).multiplyScalar(n)}projectOnPlane(t){return hc.copy(this).projectOnVector(t),this.sub(hc)}reflect(t){return this.sub(hc.copy(t).multiplyScalar(2*this.dot(t)))}angleTo(t){let e=Math.sqrt(this.lengthSq()*t.lengthSq());if(e===0)return Math.PI/2;let n=this.dot(t)/e;return Math.acos(de(n,-1,1))}distanceTo(t){return Math.sqrt(this.distanceToSquared(t))}distanceToSquared(t){let e=this.x-t.x,n=this.y-t.y,s=this.z-t.z;return e*e+n*n+s*s}manhattanDistanceTo(t){return Math.abs(this.x-t.x)+Math.abs(this.y-t.y)+Math.abs(this.z-t.z)}setFromSpherical(t){return this.setFromSphericalCoords(t.radius,t.phi,t.theta)}setFromSphericalCoords(t,e,n){let s=Math.sin(e)*t;return this.x=s*Math.sin(n),this.y=Math.cos(e)*t,this.z=s*Math.cos(n),this}setFromCylindrical(t){return this.setFromCylindricalCoords(t.radius,t.theta,t.y)}setFromCylindricalCoords(t,e,n){return this.x=t*Math.sin(e),this.y=n,this.z=t*Math.cos(e),this}setFromMatrixPosition(t){let e=t.elements;return this.x=e[12],this.y=e[13],this.z=e[14],this}setFromMatrixScale(t){let e=this.setFromMatrixColumn(t,0).length(),n=this.setFromMatrixColumn(t,1).length(),s=this.setFromMatrixColumn(t,2).length();return this.x=e,this.y=n,this.z=s,this}setFromMatrixColumn(t,e){return this.fromArray(t.elements,e*4)}setFromMatrix3Column(t,e){return this.fromArray(t.elements,e*3)}setFromEuler(t){return this.x=t._x,this.y=t._y,this.z=t._z,this}setFromColor(t){return this.x=t.r,this.y=t.g,this.z=t.b,this}equals(t){return t.x===this.x&&t.y===this.y&&t.z===this.z}fromArray(t,e=0){return this.x=t[e],this.y=t[e+1],this.z=t[e+2],this}toArray(t=[],e=0){return t[e]=this.x,t[e+1]=this.y,t[e+2]=this.z,t}fromBufferAttribute(t,e){return this.x=t.getX(e),this.y=t.getY(e),this.z=t.getZ(e),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this}randomDirection(){let t=Math.random()*Math.PI*2,e=Math.random()*2-1,n=Math.sqrt(1-e*e);return this.x=n*Math.cos(t),this.y=e,this.z=n*Math.sin(t),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z}};ph.prototype.isVector3=!0;var F=ph,hc=new F,ru=new Ye,mh=class mh{constructor(t,e,n,s,r,a,l,o,c){this.elements=[1,0,0,0,1,0,0,0,1],t!==void 0&&this.set(t,e,n,s,r,a,l,o,c)}set(t,e,n,s,r,a,l,o,c){let h=this.elements;return h[0]=t,h[1]=s,h[2]=l,h[3]=e,h[4]=r,h[5]=o,h[6]=n,h[7]=a,h[8]=c,this}identity(){return this.set(1,0,0,0,1,0,0,0,1),this}copy(t){let e=this.elements,n=t.elements;return e[0]=n[0],e[1]=n[1],e[2]=n[2],e[3]=n[3],e[4]=n[4],e[5]=n[5],e[6]=n[6],e[7]=n[7],e[8]=n[8],this}extractBasis(t,e,n){return t.setFromMatrix3Column(this,0),e.setFromMatrix3Column(this,1),n.setFromMatrix3Column(this,2),this}setFromMatrix4(t){let e=t.elements;return this.set(e[0],e[4],e[8],e[1],e[5],e[9],e[2],e[6],e[10]),this}multiply(t){return this.multiplyMatrices(this,t)}premultiply(t){return this.multiplyMatrices(t,this)}multiplyMatrices(t,e){let n=t.elements,s=e.elements,r=this.elements,a=n[0],l=n[3],o=n[6],c=n[1],h=n[4],f=n[7],d=n[2],p=n[5],x=n[8],M=s[0],m=s[3],u=s[6],b=s[1],A=s[4],v=s[7],S=s[2],E=s[5],R=s[8];return r[0]=a*M+l*b+o*S,r[3]=a*m+l*A+o*E,r[6]=a*u+l*v+o*R,r[1]=c*M+h*b+f*S,r[4]=c*m+h*A+f*E,r[7]=c*u+h*v+f*R,r[2]=d*M+p*b+x*S,r[5]=d*m+p*A+x*E,r[8]=d*u+p*v+x*R,this}multiplyScalar(t){let e=this.elements;return e[0]*=t,e[3]*=t,e[6]*=t,e[1]*=t,e[4]*=t,e[7]*=t,e[2]*=t,e[5]*=t,e[8]*=t,this}determinant(){let t=this.elements,e=t[0],n=t[1],s=t[2],r=t[3],a=t[4],l=t[5],o=t[6],c=t[7],h=t[8];return e*a*h-e*l*c-n*r*h+n*l*o+s*r*c-s*a*o}invert(){let t=this.elements,e=t[0],n=t[1],s=t[2],r=t[3],a=t[4],l=t[5],o=t[6],c=t[7],h=t[8],f=h*a-l*c,d=l*o-h*r,p=c*r-a*o,x=e*f+n*d+s*p;if(x===0)return this.set(0,0,0,0,0,0,0,0,0);let M=1/x;return t[0]=f*M,t[1]=(s*c-h*n)*M,t[2]=(l*n-s*a)*M,t[3]=d*M,t[4]=(h*e-s*o)*M,t[5]=(s*r-l*e)*M,t[6]=p*M,t[7]=(n*o-c*e)*M,t[8]=(a*e-n*r)*M,this}transpose(){let t,e=this.elements;return t=e[1],e[1]=e[3],e[3]=t,t=e[2],e[2]=e[6],e[6]=t,t=e[5],e[5]=e[7],e[7]=t,this}getNormalMatrix(t){return this.setFromMatrix4(t).invert().transpose()}transposeIntoArray(t){let e=this.elements;return t[0]=e[0],t[1]=e[3],t[2]=e[6],t[3]=e[1],t[4]=e[4],t[5]=e[7],t[6]=e[2],t[7]=e[5],t[8]=e[8],this}setUvTransform(t,e,n,s,r,a,l){let o=Math.cos(r),c=Math.sin(r);return this.set(n*o,n*c,-n*(o*a+c*l)+a+t,-s*c,s*o,-s*(-c*a+o*l)+l+e,0,0,1),this}scale(t,e){return Os("Matrix3: .scale() is deprecated. Use .makeScale() instead."),this.premultiply(uc.makeScale(t,e)),this}rotate(t){return Os("Matrix3: .rotate() is deprecated. Use .makeRotation() instead."),this.premultiply(uc.makeRotation(-t)),this}translate(t,e){return Os("Matrix3: .translate() is deprecated. Use .makeTranslation() instead."),this.premultiply(uc.makeTranslation(t,e)),this}makeTranslation(t,e){return t.isVector2?this.set(1,0,t.x,0,1,t.y,0,0,1):this.set(1,0,t,0,1,e,0,0,1),this}makeRotation(t){let e=Math.cos(t),n=Math.sin(t);return this.set(e,-n,0,n,e,0,0,0,1),this}makeScale(t,e){return this.set(t,0,0,0,e,0,0,0,1),this}equals(t){let e=this.elements,n=t.elements;for(let s=0;s<9;s++)if(e[s]!==n[s])return!1;return!0}fromArray(t,e=0){for(let n=0;n<9;n++)this.elements[n]=t[n+e];return this}toArray(t=[],e=0){let n=this.elements;return t[e]=n[0],t[e+1]=n[1],t[e+2]=n[2],t[e+3]=n[3],t[e+4]=n[4],t[e+5]=n[5],t[e+6]=n[6],t[e+7]=n[7],t[e+8]=n[8],t}clone(){return new this.constructor().fromArray(this.elements)}};mh.prototype.isMatrix3=!0;var Qt=mh,uc=new Qt,au=new Qt().set(.4123908,.3575843,.1804808,.212639,.7151687,.0721923,.0193308,.1191948,.9505322),ou=new Qt().set(3.2409699,-1.5373832,-.4986108,-.9692436,1.8759675,.0415551,.0556301,-.203977,1.0569715);function rp(){let i={enabled:!0,workingColorSpace:ha,spaces:{},convert:function(s,r,a){return this.enabled===!1||r===a||!r||!a||(this.spaces[r].transfer===Ae&&(s.r=Xi(s.r),s.g=Xi(s.g),s.b=Xi(s.b)),this.spaces[r].primaries!==this.spaces[a].primaries&&(s.applyMatrix3(this.spaces[r].toXYZ),s.applyMatrix3(this.spaces[a].fromXYZ)),this.spaces[a].transfer===Ae&&(s.r=br(s.r),s.g=br(s.g),s.b=br(s.b))),s},workingToColorSpace:function(s,r){return this.convert(s,this.workingColorSpace,r)},colorSpaceToWorking:function(s,r){return this.convert(s,r,this.workingColorSpace)},getPrimaries:function(s){return this.spaces[s].primaries},getTransfer:function(s){return s===$i?ua:this.spaces[s].transfer},getToneMappingMode:function(s){return this.spaces[s].outputColorSpaceConfig.toneMappingMode||"standard"},getLuminanceCoefficients:function(s,r=this.workingColorSpace){return s.fromArray(this.spaces[r].luminanceCoefficients)},define:function(s){Object.assign(this.spaces,s)},_getMatrix:function(s,r,a){return s.copy(this.spaces[r].toXYZ).multiply(this.spaces[a].fromXYZ)},_getDrawingBufferColorSpace:function(s){return this.spaces[s].outputColorSpaceConfig.drawingBufferColorSpace},_getUnpackColorSpace:function(s=this.workingColorSpace){return this.spaces[s].workingColorSpaceConfig.unpackColorSpace},fromWorkingColorSpace:function(s,r){return Os("ColorManagement: .fromWorkingColorSpace() has been renamed to .workingToColorSpace()."),i.workingToColorSpace(s,r)},toWorkingColorSpace:function(s,r){return Os("ColorManagement: .toWorkingColorSpace() has been renamed to .colorSpaceToWorking()."),i.colorSpaceToWorking(s,r)}},t=[.64,.33,.3,.6,.15,.06],e=[.2126,.7152,.0722],n=[.3127,.329];return i.define({[ha]:{primaries:t,whitePoint:n,transfer:ua,toXYZ:au,fromXYZ:ou,luminanceCoefficients:e,workingColorSpaceConfig:{unpackColorSpace:Ge},outputColorSpaceConfig:{drawingBufferColorSpace:Ge}},[Ge]:{primaries:t,whitePoint:n,transfer:Ae,toXYZ:au,fromXYZ:ou,luminanceCoefficients:e,outputColorSpaceConfig:{drawingBufferColorSpace:Ge}}}),i}var me=rp();function Xi(i){return i<.04045?i*.0773993808:Math.pow(i*.9478672986+.0521327014,2.4)}function br(i){return i<.0031308?i*12.92:1.055*Math.pow(i,.41666)-.055}var ar,Ao=class{static getDataURL(t,e="image/png"){if(/^data:/i.test(t.src)||typeof HTMLCanvasElement>"u")return t.src;let n;if(t instanceof HTMLCanvasElement)n=t;else{ar===void 0&&(ar=da("canvas")),ar.width=t.width,ar.height=t.height;let s=ar.getContext("2d");t instanceof ImageData?s.putImageData(t,0,0):s.drawImage(t,0,0,t.width,t.height),n=ar}return n.toDataURL(e)}static sRGBToLinear(t){if(typeof HTMLImageElement<"u"&&t instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&t instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&t instanceof ImageBitmap){let e=da("canvas");e.width=t.width,e.height=t.height;let n=e.getContext("2d");n.drawImage(t,0,0,t.width,t.height);let s=n.getImageData(0,0,t.width,t.height),r=s.data;for(let a=0;a<r.length;a++)r[a]=Xi(r[a]/255)*255;return n.putImageData(s,0,0),e}else if(t.data){let e=t.data.slice(0);for(let n=0;n<e.length;n++)e instanceof Uint8Array||e instanceof Uint8ClampedArray?e[n]=Math.floor(Xi(e[n]/255)*255):e[n]=Xi(e[n]);return{data:e,width:t.width,height:t.height}}else return Zt("ImageUtils.sRGBToLinear(): Unsupported image type. No color space conversion applied."),t}},ap=0,Tr=class{constructor(t=null){this.isTextureSource=!0,Object.defineProperty(this,"id",{value:ap++}),this.uuid=Or(),this.data=t,this.dataReady=!0,this.version=0}getSize(t){let e=this.data;return typeof HTMLVideoElement<"u"&&e instanceof HTMLVideoElement?t.set(e.videoWidth,e.videoHeight,0):typeof VideoFrame<"u"&&e instanceof VideoFrame?t.set(e.displayWidth,e.displayHeight,0):e!==null?t.set(e.width,e.height,e.depth||0):t.set(0,0,0),t}set needsUpdate(t){t===!0&&this.version++}toJSON(t){let e=t===void 0||typeof t=="string";if(!e&&t.images[this.uuid]!==void 0)return t.images[this.uuid];let n={uuid:this.uuid,url:""},s=this.data;if(s!==null){let r;if(Array.isArray(s)){r=[];for(let a=0,l=s.length;a<l;a++)s[a].isDataTexture?r.push(dc(s[a].image)):r.push(dc(s[a]))}else r=dc(s);n.url=r}return e||(t.images[this.uuid]=n),n}};function dc(i){return typeof HTMLImageElement<"u"&&i instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&i instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&i instanceof ImageBitmap?Ao.getDataURL(i):i.data?{data:Array.from(i.data),width:i.width,height:i.height,type:i.data.constructor.name}:(Zt("Texture: Unable to serialize Texture."),{})}var op=0,fc=new F,wn=class i extends ci{constructor(t=i.DEFAULT_IMAGE,e=i.DEFAULT_MAPPING,n=Mi,s=Mi,r=mn,a=Ms,l=$n,o=Dn,c=i.DEFAULT_ANISOTROPY,h=$i){super(),this.isTexture=!0,Object.defineProperty(this,"id",{value:op++}),this.uuid=Or(),this.name="",this.source=new Tr(t),this.mipmaps=[],this.mapping=e,this.channel=0,this.wrapS=n,this.wrapT=s,this.magFilter=r,this.minFilter=a,this.anisotropy=c,this.format=l,this.internalFormat=null,this.type=o,this.offset=new Xt(0,0),this.repeat=new Xt(1,1),this.center=new Xt(0,0),this.rotation=0,this.matrixAutoUpdate=!0,this.matrix=new Qt,this.generateMipmaps=!0,this.premultiplyAlpha=!1,this.flipY=!0,this.unpackAlignment=4,this.colorSpace=h,this.userData={},this.updateRanges=[],this.version=0,this.onUpdate=null,this.renderTarget=null,this.isRenderTargetTexture=!1,this.isArrayTexture=!!(t&&t.depth&&t.depth>1),this.pmremVersion=0,this.normalized=!1}get width(){return this.source.getSize(fc).x}get height(){return this.source.getSize(fc).y}get depth(){return this.source.getSize(fc).z}get image(){return this.source.data}set image(t){this.source.data=t}updateMatrix(){this.matrix.setUvTransform(this.offset.x,this.offset.y,this.repeat.x,this.repeat.y,this.rotation,this.center.x,this.center.y)}addUpdateRange(t,e){this.updateRanges.push({start:t,count:e})}clearUpdateRanges(){this.updateRanges.length=0}clone(){return new this.constructor().copy(this)}copy(t){return this.name=t.name,this.source=t.source,this.mipmaps=t.mipmaps.slice(0),this.mapping=t.mapping,this.channel=t.channel,this.wrapS=t.wrapS,this.wrapT=t.wrapT,this.magFilter=t.magFilter,this.minFilter=t.minFilter,this.anisotropy=t.anisotropy,this.format=t.format,this.internalFormat=t.internalFormat,this.type=t.type,this.normalized=t.normalized,this.offset.copy(t.offset),this.repeat.copy(t.repeat),this.center.copy(t.center),this.rotation=t.rotation,this.matrixAutoUpdate=t.matrixAutoUpdate,this.matrix.copy(t.matrix),this.generateMipmaps=t.generateMipmaps,this.premultiplyAlpha=t.premultiplyAlpha,this.flipY=t.flipY,this.unpackAlignment=t.unpackAlignment,this.colorSpace=t.colorSpace,this.renderTarget=t.renderTarget,this.isRenderTargetTexture=t.isRenderTargetTexture,this.isArrayTexture=t.isArrayTexture,this.userData=JSON.parse(JSON.stringify(t.userData)),this.needsUpdate=!0,this}setValues(t){for(let e in t){let n=t[e];if(n===void 0){Zt(`Texture.setValues(): parameter '${e}' has value of undefined.`);continue}let s=this[e];if(s===void 0){Zt(`Texture.setValues(): property '${e}' does not exist.`);continue}s&&n&&s.isVector2&&n.isVector2||s&&n&&s.isVector3&&n.isVector3||s&&n&&s.isMatrix3&&n.isMatrix3?s.copy(n):this[e]=n}}toJSON(t){let e=t===void 0||typeof t=="string";if(!e&&t.textures[this.uuid]!==void 0)return t.textures[this.uuid];let n={metadata:{version:4.7,type:"Texture",generator:"Texture.toJSON"},uuid:this.uuid,name:this.name,image:this.source.toJSON(t).uuid,mapping:this.mapping,channel:this.channel,repeat:[this.repeat.x,this.repeat.y],offset:[this.offset.x,this.offset.y],center:[this.center.x,this.center.y],rotation:this.rotation,wrap:[this.wrapS,this.wrapT],format:this.format,internalFormat:this.internalFormat,type:this.type,normalized:this.normalized,colorSpace:this.colorSpace,minFilter:this.minFilter,magFilter:this.magFilter,anisotropy:this.anisotropy,flipY:this.flipY,generateMipmaps:this.generateMipmaps,premultiplyAlpha:this.premultiplyAlpha,unpackAlignment:this.unpackAlignment};return Object.keys(this.userData).length>0&&(n.userData=this.userData),e||(t.textures[this.uuid]=n),n}dispose(){this.dispatchEvent({type:"dispose"})}transformUv(t){if(this.mapping!==Qc)return t;if(t.applyMatrix3(this.matrix),t.x<0||t.x>1)switch(this.wrapS){case Si:t.x=t.x-Math.floor(t.x);break;case Mi:t.x=t.x<0?0:1;break;case wo:Math.abs(Math.floor(t.x)%2)===1?t.x=Math.ceil(t.x)-t.x:t.x=t.x-Math.floor(t.x);break}if(t.y<0||t.y>1)switch(this.wrapT){case Si:t.y=t.y-Math.floor(t.y);break;case Mi:t.y=t.y<0?0:1;break;case wo:Math.abs(Math.floor(t.y)%2)===1?t.y=Math.ceil(t.y)-t.y:t.y=t.y-Math.floor(t.y);break}return this.flipY&&(t.y=1-t.y),t}set needsUpdate(t){t===!0&&(this.version++,this.source.needsUpdate=!0)}set needsPMREMUpdate(t){t===!0&&this.pmremVersion++}};wn.DEFAULT_IMAGE=null;wn.DEFAULT_MAPPING=Qc;wn.DEFAULT_ANISOTROPY=1;var gh=class gh{constructor(t=0,e=0,n=0,s=1){this.x=t,this.y=e,this.z=n,this.w=s}get width(){return this.z}set width(t){this.z=t}get height(){return this.w}set height(t){this.w=t}set(t,e,n,s){return this.x=t,this.y=e,this.z=n,this.w=s,this}setScalar(t){return this.x=t,this.y=t,this.z=t,this.w=t,this}setX(t){return this.x=t,this}setY(t){return this.y=t,this}setZ(t){return this.z=t,this}setW(t){return this.w=t,this}setComponent(t,e){switch(t){case 0:this.x=e;break;case 1:this.y=e;break;case 2:this.z=e;break;case 3:this.w=e;break;default:throw new Error("THREE.Vector4: index is out of range: "+t)}return this}getComponent(t){switch(t){case 0:return this.x;case 1:return this.y;case 2:return this.z;case 3:return this.w;default:throw new Error("THREE.Vector4: index is out of range: "+t)}}clone(){return new this.constructor(this.x,this.y,this.z,this.w)}copy(t){return this.x=t.x,this.y=t.y,this.z=t.z,this.w=t.w!==void 0?t.w:1,this}add(t){return this.x+=t.x,this.y+=t.y,this.z+=t.z,this.w+=t.w,this}addScalar(t){return this.x+=t,this.y+=t,this.z+=t,this.w+=t,this}addVectors(t,e){return this.x=t.x+e.x,this.y=t.y+e.y,this.z=t.z+e.z,this.w=t.w+e.w,this}addScaledVector(t,e){return this.x+=t.x*e,this.y+=t.y*e,this.z+=t.z*e,this.w+=t.w*e,this}sub(t){return this.x-=t.x,this.y-=t.y,this.z-=t.z,this.w-=t.w,this}subScalar(t){return this.x-=t,this.y-=t,this.z-=t,this.w-=t,this}subVectors(t,e){return this.x=t.x-e.x,this.y=t.y-e.y,this.z=t.z-e.z,this.w=t.w-e.w,this}multiply(t){return this.x*=t.x,this.y*=t.y,this.z*=t.z,this.w*=t.w,this}multiplyScalar(t){return this.x*=t,this.y*=t,this.z*=t,this.w*=t,this}applyMatrix4(t){let e=this.x,n=this.y,s=this.z,r=this.w,a=t.elements;return this.x=a[0]*e+a[4]*n+a[8]*s+a[12]*r,this.y=a[1]*e+a[5]*n+a[9]*s+a[13]*r,this.z=a[2]*e+a[6]*n+a[10]*s+a[14]*r,this.w=a[3]*e+a[7]*n+a[11]*s+a[15]*r,this}divide(t){return this.x/=t.x,this.y/=t.y,this.z/=t.z,this.w/=t.w,this}divideScalar(t){return this.multiplyScalar(1/t)}setAxisAngleFromQuaternion(t){this.w=2*Math.acos(t.w);let e=Math.sqrt(1-t.w*t.w);return e<1e-4?(this.x=1,this.y=0,this.z=0):(this.x=t.x/e,this.y=t.y/e,this.z=t.z/e),this}setAxisAngleFromRotationMatrix(t){let e,n,s,r,o=t.elements,c=o[0],h=o[4],f=o[8],d=o[1],p=o[5],x=o[9],M=o[2],m=o[6],u=o[10];if(Math.abs(h-d)<.01&&Math.abs(f-M)<.01&&Math.abs(x-m)<.01){if(Math.abs(h+d)<.1&&Math.abs(f+M)<.1&&Math.abs(x+m)<.1&&Math.abs(c+p+u-3)<.1)return this.set(1,0,0,0),this;e=Math.PI;let A=(c+1)/2,v=(p+1)/2,S=(u+1)/2,E=(h+d)/4,R=(f+M)/4,g=(x+m)/4;return A>v&&A>S?A<.01?(n=0,s=.707106781,r=.707106781):(n=Math.sqrt(A),s=E/n,r=R/n):v>S?v<.01?(n=.707106781,s=0,r=.707106781):(s=Math.sqrt(v),n=E/s,r=g/s):S<.01?(n=.707106781,s=.707106781,r=0):(r=Math.sqrt(S),n=R/r,s=g/r),this.set(n,s,r,e),this}let b=Math.sqrt((m-x)*(m-x)+(f-M)*(f-M)+(d-h)*(d-h));return Math.abs(b)<.001&&(b=1),this.x=(m-x)/b,this.y=(f-M)/b,this.z=(d-h)/b,this.w=Math.acos((c+p+u-1)/2),this}setFromMatrixPosition(t){let e=t.elements;return this.x=e[12],this.y=e[13],this.z=e[14],this.w=e[15],this}min(t){return this.x=Math.min(this.x,t.x),this.y=Math.min(this.y,t.y),this.z=Math.min(this.z,t.z),this.w=Math.min(this.w,t.w),this}max(t){return this.x=Math.max(this.x,t.x),this.y=Math.max(this.y,t.y),this.z=Math.max(this.z,t.z),this.w=Math.max(this.w,t.w),this}clamp(t,e){return this.x=de(this.x,t.x,e.x),this.y=de(this.y,t.y,e.y),this.z=de(this.z,t.z,e.z),this.w=de(this.w,t.w,e.w),this}clampScalar(t,e){return this.x=de(this.x,t,e),this.y=de(this.y,t,e),this.z=de(this.z,t,e),this.w=de(this.w,t,e),this}clampLength(t,e){let n=this.length();return this.divideScalar(n||1).multiplyScalar(de(n,t,e))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this.w=Math.floor(this.w),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this.w=Math.ceil(this.w),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this.w=Math.round(this.w),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this.w=Math.trunc(this.w),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this.w=-this.w,this}dot(t){return this.x*t.x+this.y*t.y+this.z*t.z+this.w*t.w}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)+Math.abs(this.w)}normalize(){return this.divideScalar(this.length()||1)}setLength(t){return this.normalize().multiplyScalar(t)}lerp(t,e){return this.x+=(t.x-this.x)*e,this.y+=(t.y-this.y)*e,this.z+=(t.z-this.z)*e,this.w+=(t.w-this.w)*e,this}lerpVectors(t,e,n){return this.x=t.x+(e.x-t.x)*n,this.y=t.y+(e.y-t.y)*n,this.z=t.z+(e.z-t.z)*n,this.w=t.w+(e.w-t.w)*n,this}equals(t){return t.x===this.x&&t.y===this.y&&t.z===this.z&&t.w===this.w}fromArray(t,e=0){return this.x=t[e],this.y=t[e+1],this.z=t[e+2],this.w=t[e+3],this}toArray(t=[],e=0){return t[e]=this.x,t[e+1]=this.y,t[e+2]=this.z,t[e+3]=this.w,t}fromBufferAttribute(t,e){return this.x=t.getX(e),this.y=t.getY(e),this.z=t.getZ(e),this.w=t.getW(e),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this.w=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z,yield this.w}};gh.prototype.isVector4=!0;var ke=gh,Ro=class extends ci{constructor(t=1,e=1,n={}){super(),n=Object.assign({generateMipmaps:!1,internalFormat:null,minFilter:mn,depthBuffer:!0,stencilBuffer:!1,resolveColorBuffer:!0,resolveDepthBuffer:!0,resolveStencilBuffer:!0,storeMultisampledColorBuffer:!0,storeMultisampledDepthBuffer:!0,storeMultisampledStencilBuffer:!0,depthTexture:null,samples:0,count:1,depth:1,multiview:!1,useArrayDepthTexture:!1},n),this.isRenderTarget=!0,this.width=t,this.height=e,this.depth=n.depth,this.scissor=new ke(0,0,t,e),this.scissorTest=!1,this.viewport=new ke(0,0,t,e),this.textures=[];let s={width:t,height:e,depth:n.depth},r=new wn(s),a=n.count;for(let l=0;l<a;l++)this.textures[l]=r.clone(),this.textures[l].isRenderTargetTexture=!0,this.textures[l].renderTarget=this;this._setTextureOptions(n),this.depthBuffer=n.depthBuffer,this.stencilBuffer=n.stencilBuffer,this.resolveColorBuffer=n.resolveColorBuffer,this.resolveDepthBuffer=n.resolveDepthBuffer,this.resolveStencilBuffer=n.resolveStencilBuffer,this.storeMultisampledColorBuffer=n.storeMultisampledColorBuffer,this.storeMultisampledDepthBuffer=n.storeMultisampledDepthBuffer,this.storeMultisampledStencilBuffer=n.storeMultisampledStencilBuffer,this._depthTexture=null,this.depthTexture=n.depthTexture,this.samples=n.samples,this.multiview=n.multiview,this.useArrayDepthTexture=n.useArrayDepthTexture}_setTextureOptions(t={}){let e={minFilter:mn,generateMipmaps:!1,flipY:!1,internalFormat:null};t.mapping!==void 0&&(e.mapping=t.mapping),t.wrapS!==void 0&&(e.wrapS=t.wrapS),t.wrapT!==void 0&&(e.wrapT=t.wrapT),t.wrapR!==void 0&&(e.wrapR=t.wrapR),t.magFilter!==void 0&&(e.magFilter=t.magFilter),t.minFilter!==void 0&&(e.minFilter=t.minFilter),t.format!==void 0&&(e.format=t.format),t.type!==void 0&&(e.type=t.type),t.anisotropy!==void 0&&(e.anisotropy=t.anisotropy),t.colorSpace!==void 0&&(e.colorSpace=t.colorSpace),t.flipY!==void 0&&(e.flipY=t.flipY),t.generateMipmaps!==void 0&&(e.generateMipmaps=t.generateMipmaps),t.internalFormat!==void 0&&(e.internalFormat=t.internalFormat);for(let n=0;n<this.textures.length;n++)this.textures[n].setValues(e)}get texture(){return this.textures[0]}set texture(t){this.textures[0]=t}set depthTexture(t){this._depthTexture!==null&&this._depthTexture.renderTarget===this&&(this._depthTexture.renderTarget=null),t!==null&&t.renderTarget===null&&(t.renderTarget=this),this._depthTexture=t}get depthTexture(){return this._depthTexture}setSize(t,e,n=1){if(this.width!==t||this.height!==e||this.depth!==n){this.width=t,this.height=e,this.depth=n;for(let s=0,r=this.textures.length;s<r;s++)this.textures[s].image.width=t,this.textures[s].image.height=e,this.textures[s].image.depth=n,this.textures[s].isData3DTexture!==!0&&(this.textures[s].isArrayTexture=this.textures[s].image.depth>1);this.dispose()}this.viewport.set(0,0,t,e),this.scissor.set(0,0,t,e)}clone(){return new this.constructor().copy(this)}copy(t){this.width=t.width,this.height=t.height,this.depth=t.depth,this.scissor.copy(t.scissor),this.scissorTest=t.scissorTest,this.viewport.copy(t.viewport),this.textures.length=0;for(let e=0,n=t.textures.length;e<n;e++){this.textures[e]=t.textures[e].clone(),this.textures[e].isRenderTargetTexture=!0,this.textures[e].renderTarget=this;let s=Object.assign({},t.textures[e].image);this.textures[e].source=new Tr(s)}if(this.depthBuffer=t.depthBuffer,this.stencilBuffer=t.stencilBuffer,this.resolveColorBuffer=t.resolveColorBuffer,this.resolveDepthBuffer=t.resolveDepthBuffer,this.resolveStencilBuffer=t.resolveStencilBuffer,this.storeMultisampledColorBuffer=t.storeMultisampledColorBuffer,this.storeMultisampledDepthBuffer=t.storeMultisampledDepthBuffer,this.storeMultisampledStencilBuffer=t.storeMultisampledStencilBuffer,t.depthTexture!==null)if(t.depthTexture.renderTarget===t){let e=t.depthTexture.clone();e.renderTarget=null,this.depthTexture=e}else this.depthTexture=t.depthTexture;return this.samples=t.samples,this.multiview=t.multiview,this.useArrayDepthTexture=t.useArrayDepthTexture,this}dispose(){this.dispatchEvent({type:"dispose"})}},In=class extends Ro{constructor(t=1,e=1,n={}){super(t,e,n),this.isWebGLRenderTarget=!0}},fa=class extends wn{constructor(t=null,e=1,n=1,s=1){super(null),this.isDataArrayTexture=!0,this.image={data:t,width:e,height:n,depth:s},this.magFilter=an,this.minFilter=an,this.wrapR=Mi,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1,this.layerUpdates=new Set}copy(t){return super.copy(t),this.wrapR=t.wrapR,this}addLayerUpdate(t){this.layerUpdates.add(t)}clearLayerUpdates(){this.layerUpdates.clear()}};var Co=class extends wn{constructor(t=null,e=1,n=1,s=1){super(null),this.isData3DTexture=!0,this.image={data:t,width:e,height:n,depth:s},this.magFilter=an,this.minFilter=an,this.wrapR=Mi,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}copy(t){return super.copy(t),this.wrapR=t.wrapR,this}};var Yo=class Yo{constructor(t,e,n,s,r,a,l,o,c,h,f,d,p,x,M,m){this.elements=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],t!==void 0&&this.set(t,e,n,s,r,a,l,o,c,h,f,d,p,x,M,m)}set(t,e,n,s,r,a,l,o,c,h,f,d,p,x,M,m){let u=this.elements;return u[0]=t,u[4]=e,u[8]=n,u[12]=s,u[1]=r,u[5]=a,u[9]=l,u[13]=o,u[2]=c,u[6]=h,u[10]=f,u[14]=d,u[3]=p,u[7]=x,u[11]=M,u[15]=m,this}identity(){return this.set(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1),this}clone(){return new Yo().fromArray(this.elements)}copy(t){let e=this.elements,n=t.elements;return e[0]=n[0],e[1]=n[1],e[2]=n[2],e[3]=n[3],e[4]=n[4],e[5]=n[5],e[6]=n[6],e[7]=n[7],e[8]=n[8],e[9]=n[9],e[10]=n[10],e[11]=n[11],e[12]=n[12],e[13]=n[13],e[14]=n[14],e[15]=n[15],this}copyPosition(t){let e=this.elements,n=t.elements;return e[12]=n[12],e[13]=n[13],e[14]=n[14],this}setFromMatrix3(t){let e=t.elements;return this.set(e[0],e[3],e[6],0,e[1],e[4],e[7],0,e[2],e[5],e[8],0,0,0,0,1),this}extractBasis(t,e,n){return this.determinantAffine()===0?(t.set(1,0,0),e.set(0,1,0),n.set(0,0,1),this):(t.setFromMatrixColumn(this,0),e.setFromMatrixColumn(this,1),n.setFromMatrixColumn(this,2),this)}makeBasis(t,e,n){return this.set(t.x,e.x,n.x,0,t.y,e.y,n.y,0,t.z,e.z,n.z,0,0,0,0,1),this}extractRotation(t){if(t.determinantAffine()===0)return this.identity();let e=this.elements,n=t.elements,s=1/or.setFromMatrixColumn(t,0).length(),r=1/or.setFromMatrixColumn(t,1).length(),a=1/or.setFromMatrixColumn(t,2).length();return e[0]=n[0]*s,e[1]=n[1]*s,e[2]=n[2]*s,e[3]=0,e[4]=n[4]*r,e[5]=n[5]*r,e[6]=n[6]*r,e[7]=0,e[8]=n[8]*a,e[9]=n[9]*a,e[10]=n[10]*a,e[11]=0,e[12]=0,e[13]=0,e[14]=0,e[15]=1,this}makeRotationFromEuler(t){let e=this.elements,n=t.x,s=t.y,r=t.z,a=Math.cos(n),l=Math.sin(n),o=Math.cos(s),c=Math.sin(s),h=Math.cos(r),f=Math.sin(r);if(t.order==="XYZ"){let d=a*h,p=a*f,x=l*h,M=l*f;e[0]=o*h,e[4]=-o*f,e[8]=c,e[1]=p+x*c,e[5]=d-M*c,e[9]=-l*o,e[2]=M-d*c,e[6]=x+p*c,e[10]=a*o}else if(t.order==="YXZ"){let d=o*h,p=o*f,x=c*h,M=c*f;e[0]=d+M*l,e[4]=x*l-p,e[8]=a*c,e[1]=a*f,e[5]=a*h,e[9]=-l,e[2]=p*l-x,e[6]=M+d*l,e[10]=a*o}else if(t.order==="ZXY"){let d=o*h,p=o*f,x=c*h,M=c*f;e[0]=d-M*l,e[4]=-a*f,e[8]=x+p*l,e[1]=p+x*l,e[5]=a*h,e[9]=M-d*l,e[2]=-a*c,e[6]=l,e[10]=a*o}else if(t.order==="ZYX"){let d=a*h,p=a*f,x=l*h,M=l*f;e[0]=o*h,e[4]=x*c-p,e[8]=d*c+M,e[1]=o*f,e[5]=M*c+d,e[9]=p*c-x,e[2]=-c,e[6]=l*o,e[10]=a*o}else if(t.order==="YZX"){let d=a*o,p=a*c,x=l*o,M=l*c;e[0]=o*h,e[4]=M-d*f,e[8]=x*f+p,e[1]=f,e[5]=a*h,e[9]=-l*h,e[2]=-c*h,e[6]=p*f+x,e[10]=d-M*f}else if(t.order==="XZY"){let d=a*o,p=a*c,x=l*o,M=l*c;e[0]=o*h,e[4]=-f,e[8]=c*h,e[1]=d*f+M,e[5]=a*h,e[9]=p*f-x,e[2]=x*f-p,e[6]=l*h,e[10]=M*f+d}return e[3]=0,e[7]=0,e[11]=0,e[12]=0,e[13]=0,e[14]=0,e[15]=1,this}makeRotationFromQuaternion(t){return this.compose(lp,t,cp)}lookAt(t,e,n){let s=this.elements;return Bn.subVectors(t,e),Bn.lengthSq()===0&&(Bn.z=1),Bn.normalize(),as.crossVectors(n,Bn),as.lengthSq()===0&&(Math.abs(n.z)===1?Bn.x+=1e-4:Bn.z+=1e-4,Bn.normalize(),as.crossVectors(n,Bn)),as.normalize(),$a.crossVectors(Bn,as),s[0]=as.x,s[4]=$a.x,s[8]=Bn.x,s[1]=as.y,s[5]=$a.y,s[9]=Bn.y,s[2]=as.z,s[6]=$a.z,s[10]=Bn.z,this}multiply(t){return this.multiplyMatrices(this,t)}premultiply(t){return this.multiplyMatrices(t,this)}multiplyMatrices(t,e){let n=t.elements,s=e.elements,r=this.elements,a=n[0],l=n[4],o=n[8],c=n[12],h=n[1],f=n[5],d=n[9],p=n[13],x=n[2],M=n[6],m=n[10],u=n[14],b=n[3],A=n[7],v=n[11],S=n[15],E=s[0],R=s[4],g=s[8],w=s[12],T=s[1],C=s[5],D=s[9],V=s[13],U=s[2],z=s[6],q=s[10],N=s[14],G=s[3],X=s[7],K=s[11],nt=s[15];return r[0]=a*E+l*T+o*U+c*G,r[4]=a*R+l*C+o*z+c*X,r[8]=a*g+l*D+o*q+c*K,r[12]=a*w+l*V+o*N+c*nt,r[1]=h*E+f*T+d*U+p*G,r[5]=h*R+f*C+d*z+p*X,r[9]=h*g+f*D+d*q+p*K,r[13]=h*w+f*V+d*N+p*nt,r[2]=x*E+M*T+m*U+u*G,r[6]=x*R+M*C+m*z+u*X,r[10]=x*g+M*D+m*q+u*K,r[14]=x*w+M*V+m*N+u*nt,r[3]=b*E+A*T+v*U+S*G,r[7]=b*R+A*C+v*z+S*X,r[11]=b*g+A*D+v*q+S*K,r[15]=b*w+A*V+v*N+S*nt,this}multiplyScalar(t){let e=this.elements;return e[0]*=t,e[4]*=t,e[8]*=t,e[12]*=t,e[1]*=t,e[5]*=t,e[9]*=t,e[13]*=t,e[2]*=t,e[6]*=t,e[10]*=t,e[14]*=t,e[3]*=t,e[7]*=t,e[11]*=t,e[15]*=t,this}determinant(){let t=this.elements,e=t[0],n=t[4],s=t[8],r=t[12],a=t[1],l=t[5],o=t[9],c=t[13],h=t[2],f=t[6],d=t[10],p=t[14],x=t[3],M=t[7],m=t[11],u=t[15],b=o*p-c*d,A=l*p-c*f,v=l*d-o*f,S=a*p-c*h,E=a*d-o*h,R=a*f-l*h;return e*(M*b-m*A+u*v)-n*(x*b-m*S+u*E)+s*(x*A-M*S+u*R)-r*(x*v-M*E+m*R)}determinantAffine(){let t=this.elements,e=t[0],n=t[4],s=t[8],r=t[1],a=t[5],l=t[9],o=t[2],c=t[6],h=t[10];return e*(a*h-l*c)-n*(r*h-l*o)+s*(r*c-a*o)}transpose(){let t=this.elements,e;return e=t[1],t[1]=t[4],t[4]=e,e=t[2],t[2]=t[8],t[8]=e,e=t[6],t[6]=t[9],t[9]=e,e=t[3],t[3]=t[12],t[12]=e,e=t[7],t[7]=t[13],t[13]=e,e=t[11],t[11]=t[14],t[14]=e,this}setPosition(t,e,n){let s=this.elements;return t.isVector3?(s[12]=t.x,s[13]=t.y,s[14]=t.z):(s[12]=t,s[13]=e,s[14]=n),this}invert(){let t=this.elements,e=t[0],n=t[1],s=t[2],r=t[3],a=t[4],l=t[5],o=t[6],c=t[7],h=t[8],f=t[9],d=t[10],p=t[11],x=t[12],M=t[13],m=t[14],u=t[15],b=e*l-n*a,A=e*o-s*a,v=e*c-r*a,S=n*o-s*l,E=n*c-r*l,R=s*c-r*o,g=h*M-f*x,w=h*m-d*x,T=h*u-p*x,C=f*m-d*M,D=f*u-p*M,V=d*u-p*m,U=b*V-A*D+v*C+S*T-E*w+R*g;if(U===0)return this.set(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);let z=1/U;return t[0]=(l*V-o*D+c*C)*z,t[1]=(s*D-n*V-r*C)*z,t[2]=(M*R-m*E+u*S)*z,t[3]=(d*E-f*R-p*S)*z,t[4]=(o*T-a*V-c*w)*z,t[5]=(e*V-s*T+r*w)*z,t[6]=(m*v-x*R-u*A)*z,t[7]=(h*R-d*v+p*A)*z,t[8]=(a*D-l*T+c*g)*z,t[9]=(n*T-e*D-r*g)*z,t[10]=(x*E-M*v+u*b)*z,t[11]=(f*v-h*E-p*b)*z,t[12]=(l*w-a*C-o*g)*z,t[13]=(e*C-n*w+s*g)*z,t[14]=(M*A-x*S-m*b)*z,t[15]=(h*S-f*A+d*b)*z,this}scale(t){let e=this.elements,n=t.x,s=t.y,r=t.z;return e[0]*=n,e[4]*=s,e[8]*=r,e[1]*=n,e[5]*=s,e[9]*=r,e[2]*=n,e[6]*=s,e[10]*=r,e[3]*=n,e[7]*=s,e[11]*=r,this}getMaxScaleOnAxis(){let t=this.elements,e=t[0]*t[0]+t[1]*t[1]+t[2]*t[2],n=t[4]*t[4]+t[5]*t[5]+t[6]*t[6],s=t[8]*t[8]+t[9]*t[9]+t[10]*t[10];return Math.sqrt(Math.max(e,n,s))}makeTranslation(t,e,n){return t.isVector3?this.set(1,0,0,t.x,0,1,0,t.y,0,0,1,t.z,0,0,0,1):this.set(1,0,0,t,0,1,0,e,0,0,1,n,0,0,0,1),this}makeRotationX(t){let e=Math.cos(t),n=Math.sin(t);return this.set(1,0,0,0,0,e,-n,0,0,n,e,0,0,0,0,1),this}makeRotationY(t){let e=Math.cos(t),n=Math.sin(t);return this.set(e,0,n,0,0,1,0,0,-n,0,e,0,0,0,0,1),this}makeRotationZ(t){let e=Math.cos(t),n=Math.sin(t);return this.set(e,-n,0,0,n,e,0,0,0,0,1,0,0,0,0,1),this}makeRotationAxis(t,e){let n=Math.cos(e),s=Math.sin(e),r=1-n,a=t.x,l=t.y,o=t.z,c=r*a,h=r*l;return this.set(c*a+n,c*l-s*o,c*o+s*l,0,c*l+s*o,h*l+n,h*o-s*a,0,c*o-s*l,h*o+s*a,r*o*o+n,0,0,0,0,1),this}makeScale(t,e,n){return this.set(t,0,0,0,0,e,0,0,0,0,n,0,0,0,0,1),this}makeShear(t,e,n,s,r,a){return this.set(1,n,r,0,t,1,a,0,e,s,1,0,0,0,0,1),this}compose(t,e,n){let s=this.elements,r=e._x,a=e._y,l=e._z,o=e._w,c=r+r,h=a+a,f=l+l,d=r*c,p=r*h,x=r*f,M=a*h,m=a*f,u=l*f,b=o*c,A=o*h,v=o*f,S=n.x,E=n.y,R=n.z;return s[0]=(1-(M+u))*S,s[1]=(p+v)*S,s[2]=(x-A)*S,s[3]=0,s[4]=(p-v)*E,s[5]=(1-(d+u))*E,s[6]=(m+b)*E,s[7]=0,s[8]=(x+A)*R,s[9]=(m-b)*R,s[10]=(1-(d+M))*R,s[11]=0,s[12]=t.x,s[13]=t.y,s[14]=t.z,s[15]=1,this}decompose(t,e,n){let s=this.elements;t.x=s[12],t.y=s[13],t.z=s[14];let r=this.determinantAffine();if(r===0)return n.set(1,1,1),e.identity(),this;let a=or.set(s[0],s[1],s[2]).length(),l=or.set(s[4],s[5],s[6]).length(),o=or.set(s[8],s[9],s[10]).length();r<0&&(a=-a),ri.copy(this);let c=1/a,h=1/l,f=1/o;return ri.elements[0]*=c,ri.elements[1]*=c,ri.elements[2]*=c,ri.elements[4]*=h,ri.elements[5]*=h,ri.elements[6]*=h,ri.elements[8]*=f,ri.elements[9]*=f,ri.elements[10]*=f,e.setFromRotationMatrix(ri),n.x=a,n.y=l,n.z=o,this}makePerspective(t,e,n,s,r,a,l=li,o=!1){let c=this.elements,h=2*r/(e-t),f=2*r/(n-s),d=(e+t)/(e-t),p=(n+s)/(n-s),x,M;if(o)x=r/(a-r),M=a*r/(a-r);else if(l===li)x=-(a+r)/(a-r),M=-2*a*r/(a-r);else if(l===Sr)x=-a/(a-r),M=-a*r/(a-r);else throw new Error("THREE.Matrix4.makePerspective(): Invalid coordinate system: "+l);return c[0]=h,c[4]=0,c[8]=d,c[12]=0,c[1]=0,c[5]=f,c[9]=p,c[13]=0,c[2]=0,c[6]=0,c[10]=x,c[14]=M,c[3]=0,c[7]=0,c[11]=-1,c[15]=0,this}makeOrthographic(t,e,n,s,r,a,l=li,o=!1){let c=this.elements,h=2/(e-t),f=2/(n-s),d=-(e+t)/(e-t),p=-(n+s)/(n-s),x,M;if(o)x=1/(a-r),M=a/(a-r);else if(l===li)x=-2/(a-r),M=-(a+r)/(a-r);else if(l===Sr)x=-1/(a-r),M=-r/(a-r);else throw new Error("THREE.Matrix4.makeOrthographic(): Invalid coordinate system: "+l);return c[0]=h,c[4]=0,c[8]=0,c[12]=d,c[1]=0,c[5]=f,c[9]=0,c[13]=p,c[2]=0,c[6]=0,c[10]=x,c[14]=M,c[3]=0,c[7]=0,c[11]=0,c[15]=1,this}equals(t){let e=this.elements,n=t.elements;for(let s=0;s<16;s++)if(e[s]!==n[s])return!1;return!0}fromArray(t,e=0){for(let n=0;n<16;n++)this.elements[n]=t[n+e];return this}toArray(t=[],e=0){let n=this.elements;return t[e]=n[0],t[e+1]=n[1],t[e+2]=n[2],t[e+3]=n[3],t[e+4]=n[4],t[e+5]=n[5],t[e+6]=n[6],t[e+7]=n[7],t[e+8]=n[8],t[e+9]=n[9],t[e+10]=n[10],t[e+11]=n[11],t[e+12]=n[12],t[e+13]=n[13],t[e+14]=n[14],t[e+15]=n[15],t}};Yo.prototype.isMatrix4=!0;var ge=Yo,or=new F,ri=new ge,lp=new F(0,0,0),cp=new F(1,1,1),as=new F,$a=new F,Bn=new F,lu=new ge,cu=new Ye,Ln=class i{constructor(t=0,e=0,n=0,s=i.DEFAULT_ORDER){this.isEuler=!0,this._x=t,this._y=e,this._z=n,this._order=s}get x(){return this._x}set x(t){this._x=t,this._onChangeCallback()}get y(){return this._y}set y(t){this._y=t,this._onChangeCallback()}get z(){return this._z}set z(t){this._z=t,this._onChangeCallback()}get order(){return this._order}set order(t){this._order=t,this._onChangeCallback()}set(t,e,n,s=this._order){return this._x=t,this._y=e,this._z=n,this._order=s,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._order)}copy(t){return this._x=t._x,this._y=t._y,this._z=t._z,this._order=t._order,this._onChangeCallback(),this}setFromRotationMatrix(t,e=this._order,n=!0){let s=t.elements,r=s[0],a=s[4],l=s[8],o=s[1],c=s[5],h=s[9],f=s[2],d=s[6],p=s[10];switch(e){case"XYZ":this._y=Math.asin(de(l,-1,1)),Math.abs(l)<.9999999?(this._x=Math.atan2(-h,p),this._z=Math.atan2(-a,r)):(this._x=Math.atan2(d,c),this._z=0);break;case"YXZ":this._x=Math.asin(-de(h,-1,1)),Math.abs(h)<.9999999?(this._y=Math.atan2(l,p),this._z=Math.atan2(o,c)):(this._y=Math.atan2(-f,r),this._z=0);break;case"ZXY":this._x=Math.asin(de(d,-1,1)),Math.abs(d)<.9999999?(this._y=Math.atan2(-f,p),this._z=Math.atan2(-a,c)):(this._y=0,this._z=Math.atan2(o,r));break;case"ZYX":this._y=Math.asin(-de(f,-1,1)),Math.abs(f)<.9999999?(this._x=Math.atan2(d,p),this._z=Math.atan2(o,r)):(this._x=0,this._z=Math.atan2(-a,c));break;case"YZX":this._z=Math.asin(de(o,-1,1)),Math.abs(o)<.9999999?(this._x=Math.atan2(-h,c),this._y=Math.atan2(-f,r)):(this._x=0,this._y=Math.atan2(l,p));break;case"XZY":this._z=Math.asin(-de(a,-1,1)),Math.abs(a)<.9999999?(this._x=Math.atan2(d,c),this._y=Math.atan2(l,r)):(this._x=Math.atan2(-h,p),this._y=0);break;default:Zt("Euler: .setFromRotationMatrix() encountered an unknown order: "+e)}return this._order=e,n===!0&&this._onChangeCallback(),this}setFromQuaternion(t,e,n){return lu.makeRotationFromQuaternion(t),this.setFromRotationMatrix(lu,e,n)}setFromVector3(t,e=this._order){return this.set(t.x,t.y,t.z,e)}reorder(t){return cu.setFromEuler(this),this.setFromQuaternion(cu,t)}equals(t){return t._x===this._x&&t._y===this._y&&t._z===this._z&&t._order===this._order}fromArray(t){return this._x=t[0],this._y=t[1],this._z=t[2],t[3]!==void 0&&(this._order=t[3]),this._onChangeCallback(),this}toArray(t=[],e=0){return t[e]=this._x,t[e+1]=this._y,t[e+2]=this._z,t[e+3]=this._order,t}_onChange(t){return this._onChangeCallback=t,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._order}};Ln.DEFAULT_ORDER="XYZ";var Ar=class{constructor(){this.mask=1}set(t){this.mask=(1<<t|0)>>>0}enable(t){this.mask|=1<<t|0}enableAll(){this.mask=-1}toggle(t){this.mask^=1<<t|0}disable(t){this.mask&=~(1<<t|0)}disableAll(){this.mask=0}test(t){return(this.mask&t.mask)!==0}isEnabled(t){return(this.mask&(1<<t|0))!==0}},hp=0,hu=new F,lr=new Ye,ki=new ge,Ka=new F,ea=new F,up=new F,dp=new Ye,uu=new F(1,0,0),du=new F(0,1,0),fu=new F(0,0,1),pu={type:"added"},fp={type:"removed"},cr={type:"childadded",child:null},pc={type:"childremoved",child:null},on=class i extends ci{constructor(){super(),this.isObject3D=!0,Object.defineProperty(this,"id",{value:hp++}),this.uuid=Or(),this.name="",this.type="Object3D",this.parent=null,this.children=[],this.up=i.DEFAULT_UP.clone();let t=new F,e=new Ln,n=new Ye,s=new F(1,1,1);function r(){n.setFromEuler(e,!1)}function a(){e.setFromQuaternion(n,void 0,!1)}e._onChange(r),n._onChange(a),Object.defineProperties(this,{position:{configurable:!0,enumerable:!0,value:t},rotation:{configurable:!0,enumerable:!0,value:e},quaternion:{configurable:!0,enumerable:!0,value:n},scale:{configurable:!0,enumerable:!0,value:s},modelViewMatrix:{value:new ge},normalMatrix:{value:new Qt}}),this.matrix=new ge,this.matrixWorld=new ge,this.matrixAutoUpdate=i.DEFAULT_MATRIX_AUTO_UPDATE,this.matrixWorldAutoUpdate=i.DEFAULT_MATRIX_WORLD_AUTO_UPDATE,this.matrixWorldNeedsUpdate=!1,this.layers=new Ar,this.visible=!0,this.castShadow=!1,this.receiveShadow=!1,this.frustumCulled=!0,this.renderOrder=0,this.animations=[],this.customDepthMaterial=void 0,this.customDistanceMaterial=void 0,this.static=!1,this.userData={},this.pivot=null}onBeforeShadow(){}onAfterShadow(){}onBeforeRender(){}onAfterRender(){}applyMatrix4(t){this.matrixAutoUpdate&&this.updateMatrix(),this.matrix.premultiply(t),this.matrix.decompose(this.position,this.quaternion,this.scale)}applyQuaternion(t){return this.quaternion.premultiply(t),this}setRotationFromAxisAngle(t,e){this.quaternion.setFromAxisAngle(t,e)}setRotationFromEuler(t){this.quaternion.setFromEuler(t,!0)}setRotationFromMatrix(t){this.quaternion.setFromRotationMatrix(t)}setRotationFromQuaternion(t){this.quaternion.copy(t)}rotateOnAxis(t,e){return lr.setFromAxisAngle(t,e),this.quaternion.multiply(lr),this}rotateOnWorldAxis(t,e){return lr.setFromAxisAngle(t,e),this.quaternion.premultiply(lr),this}rotateX(t){return this.rotateOnAxis(uu,t)}rotateY(t){return this.rotateOnAxis(du,t)}rotateZ(t){return this.rotateOnAxis(fu,t)}translateOnAxis(t,e){return hu.copy(t).applyQuaternion(this.quaternion),this.position.add(hu.multiplyScalar(e)),this}translateX(t){return this.translateOnAxis(uu,t)}translateY(t){return this.translateOnAxis(du,t)}translateZ(t){return this.translateOnAxis(fu,t)}localToWorld(t){return this.updateWorldMatrix(!0,!1),t.applyMatrix4(this.matrixWorld)}worldToLocal(t){return this.updateWorldMatrix(!0,!1),t.applyMatrix4(ki.copy(this.matrixWorld).invert())}lookAt(t,e,n){t.isVector3?Ka.copy(t):Ka.set(t,e,n);let s=this.parent;this.updateWorldMatrix(!0,!1),ea.setFromMatrixPosition(this.matrixWorld),this.isCamera||this.isLight?ki.lookAt(ea,Ka,this.up):ki.lookAt(Ka,ea,this.up),this.quaternion.setFromRotationMatrix(ki),s&&(ki.extractRotation(s.matrixWorld),lr.setFromRotationMatrix(ki),this.quaternion.premultiply(lr.invert()))}add(t){if(arguments.length>1){for(let e=0;e<arguments.length;e++)this.add(arguments[e]);return this}return t===this?(Kt("Object3D.add: object can't be added as a child of itself.",t),this):(t&&t.isObject3D?(t.removeFromParent(),t.parent=this,this.children.push(t),t.dispatchEvent(pu),cr.child=t,this.dispatchEvent(cr),cr.child=null):Kt("Object3D.add: object not an instance of THREE.Object3D.",t),this)}remove(t){if(arguments.length>1){for(let n=0;n<arguments.length;n++)this.remove(arguments[n]);return this}let e=this.children.indexOf(t);return e!==-1&&(t.parent=null,this.children.splice(e,1),t.dispatchEvent(fp),pc.child=t,this.dispatchEvent(pc),pc.child=null),this}removeFromParent(){let t=this.parent;return t!==null&&t.remove(this),this}clear(){return this.remove(...this.children)}attach(t){return this.updateWorldMatrix(!0,!1),ki.copy(this.matrixWorld).invert(),t.parent!==null&&(t.parent.updateWorldMatrix(!0,!1),ki.multiply(t.parent.matrixWorld)),t.applyMatrix4(ki),t.removeFromParent(),t.parent=this,this.children.push(t),t.updateWorldMatrix(!1,!0),t.dispatchEvent(pu),cr.child=t,this.dispatchEvent(cr),cr.child=null,this}getObjectById(t){return this.getObjectByProperty("id",t)}getObjectByName(t){return this.getObjectByProperty("name",t)}getObjectByProperty(t,e){if(this[t]===e)return this;for(let n=0,s=this.children.length;n<s;n++){let a=this.children[n].getObjectByProperty(t,e);if(a!==void 0)return a}}getObjectsByProperty(t,e,n=[]){this[t]===e&&n.push(this);let s=this.children;for(let r=0,a=s.length;r<a;r++)s[r].getObjectsByProperty(t,e,n);return n}getWorldPosition(t){return this.updateWorldMatrix(!0,!1),t.setFromMatrixPosition(this.matrixWorld)}getWorldQuaternion(t){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(ea,t,up),t}getWorldScale(t){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(ea,dp,t),t}getWorldDirection(t){this.updateWorldMatrix(!0,!1);let e=this.matrixWorld.elements;return t.set(e[8],e[9],e[10]).normalize()}raycast(){}intersectsFrustum(){}traverse(t){t(this);let e=this.children;for(let n=0,s=e.length;n<s;n++)e[n].traverse(t)}traverseVisible(t){if(this.visible===!1)return;t(this);let e=this.children;for(let n=0,s=e.length;n<s;n++)e[n].traverseVisible(t)}traverseAncestors(t){let e=this.parent;e!==null&&(t(e),e.traverseAncestors(t))}updateMatrix(){this.matrix.compose(this.position,this.quaternion,this.scale);let t=this.pivot;if(t!==null){let e=t.x,n=t.y,s=t.z,r=this.matrix.elements;r[12]+=e-r[0]*e-r[4]*n-r[8]*s,r[13]+=n-r[1]*e-r[5]*n-r[9]*s,r[14]+=s-r[2]*e-r[6]*n-r[10]*s}this.matrixWorldNeedsUpdate=!0}updateMatrixWorld(t){this.matrixAutoUpdate&&this.updateMatrix(),(this.matrixWorldNeedsUpdate||t)&&(this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),this.matrixWorldNeedsUpdate=!1,t=!0);let e=this.children;for(let n=0,s=e.length;n<s;n++)e[n].updateMatrixWorld(t)}updateWorldMatrix(t,e,n=!1){let s=this.parent;if(t===!0&&s!==null&&s.updateWorldMatrix(!0,!1),this.matrixAutoUpdate&&this.updateMatrix(),(this.matrixWorldNeedsUpdate||n)&&(this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),this.matrixWorldNeedsUpdate=!1,n=!0),e===!0){let r=this.children;for(let a=0,l=r.length;a<l;a++)r[a].updateWorldMatrix(!1,!0,n)}}toJSON(t){let e=t===void 0||typeof t=="string",n={};e&&(t={geometries:{},materials:{},textures:{},images:{},shapes:{},skeletons:{},animations:{},nodes:{}},n.metadata={version:4.7,type:"Object",generator:"Object3D.toJSON"});let s={};s.uuid=this.uuid,s.type=this.type,s.name=this.name,s.castShadow=this.castShadow,s.receiveShadow=this.receiveShadow,s.visible=this.visible,s.frustumCulled=this.frustumCulled,s.renderOrder=this.renderOrder,s.static=this.static,s.matrixAutoUpdate=this.matrixAutoUpdate,Object.keys(this.userData).length>0&&(s.userData=this.userData),s.layers=this.layers.mask,s.matrix=this.matrix.toArray(),s.up=this.up.toArray(),this.pivot!==null&&(s.pivot=this.pivot.toArray()),this.morphTargetDictionary!==void 0&&(s.morphTargetDictionary=Object.assign({},this.morphTargetDictionary)),this.morphTargetInfluences!==void 0&&(s.morphTargetInfluences=this.morphTargetInfluences.slice()),this.isInstancedMesh&&(s.type="InstancedMesh",s.count=this.count,s.instanceMatrix=this.instanceMatrix.toJSON(),this.instanceColor!==null&&(s.instanceColor=this.instanceColor.toJSON())),this.isBatchedMesh&&(s.type="BatchedMesh",s.perObjectFrustumCulled=this.perObjectFrustumCulled,s.sortObjects=this.sortObjects,s.drawRanges=this._drawRanges,s.reservedRanges=this._reservedRanges,s.geometryInfo=this._geometryInfo.map(l=>({...l,boundingBox:l.boundingBox?l.boundingBox.toJSON():void 0,boundingSphere:l.boundingSphere?l.boundingSphere.toJSON():void 0})),s.instanceInfo=this._instanceInfo.map(l=>({...l})),s.availableInstanceIds=this._availableInstanceIds.slice(),s.availableGeometryIds=this._availableGeometryIds.slice(),s.nextIndexStart=this._nextIndexStart,s.nextVertexStart=this._nextVertexStart,s.geometryCount=this._geometryCount,s.maxInstanceCount=this._maxInstanceCount,s.maxVertexCount=this._maxVertexCount,s.maxIndexCount=this._maxIndexCount,s.geometryInitialized=this._geometryInitialized,s.matricesTexture=this._matricesTexture.toJSON(t),s.indirectTexture=this._indirectTexture.toJSON(t),this._colorsTexture!==null&&(s.colorsTexture=this._colorsTexture.toJSON(t)),this.boundingSphere!==null&&(s.boundingSphere=this.boundingSphere.toJSON()),this.boundingBox!==null&&(s.boundingBox=this.boundingBox.toJSON()));function r(l,o){return l[o.uuid]===void 0&&(l[o.uuid]=o.toJSON(t)),o.uuid}if(this.isScene)this.background&&(this.background.isColor?s.background=this.background.toJSON():this.background.isTexture&&(s.background=this.background.toJSON(t).uuid)),this.environment&&this.environment.isTexture&&this.environment.isRenderTargetTexture!==!0&&(s.environment=this.environment.toJSON(t).uuid);else if(this.isMesh||this.isLine||this.isPoints){s.geometry=r(t.geometries,this.geometry);let l=this.geometry.parameters;if(l!==void 0&&l.shapes!==void 0){let o=l.shapes;if(Array.isArray(o))for(let c=0,h=o.length;c<h;c++){let f=o[c];r(t.shapes,f)}else r(t.shapes,o)}}if(this.isSkinnedMesh&&(s.bindMode=this.bindMode,s.bindMatrix=this.bindMatrix.toArray(),this.skeleton!==void 0&&(r(t.skeletons,this.skeleton),s.skeleton=this.skeleton.uuid)),this.material!==void 0)if(Array.isArray(this.material)){let l=[];for(let o=0,c=this.material.length;o<c;o++)l.push(r(t.materials,this.material[o]));s.material=l}else s.material=r(t.materials,this.material);if(this.children.length>0){s.children=[];for(let l=0;l<this.children.length;l++)s.children.push(this.children[l].toJSON(t).object)}if(this.animations.length>0){s.animations=[];for(let l=0;l<this.animations.length;l++){let o=this.animations[l];s.animations.push(r(t.animations,o))}}if(e){let l=a(t.geometries),o=a(t.materials),c=a(t.textures),h=a(t.images),f=a(t.shapes),d=a(t.skeletons),p=a(t.animations),x=a(t.nodes);l.length>0&&(n.geometries=l),o.length>0&&(n.materials=o),c.length>0&&(n.textures=c),h.length>0&&(n.images=h),f.length>0&&(n.shapes=f),d.length>0&&(n.skeletons=d),p.length>0&&(n.animations=p),x.length>0&&(n.nodes=x)}return n.object=s,n;function a(l){let o=[];for(let c in l){let h=l[c];delete h.metadata,o.push(h)}return o}}clone(t){return new this.constructor().copy(this,t)}copy(t,e=!0){if(this.name=t.name,this.up.copy(t.up),this.position.copy(t.position),this.rotation.order=t.rotation.order,this.quaternion.copy(t.quaternion),this.scale.copy(t.scale),this.pivot=t.pivot!==null?t.pivot.clone():null,this.matrix.copy(t.matrix),this.matrixWorld.copy(t.matrixWorld),this.matrixAutoUpdate=t.matrixAutoUpdate,this.matrixWorldAutoUpdate=t.matrixWorldAutoUpdate,this.matrixWorldNeedsUpdate=t.matrixWorldNeedsUpdate,this.layers.mask=t.layers.mask,this.visible=t.visible,this.castShadow=t.castShadow,this.receiveShadow=t.receiveShadow,this.frustumCulled=t.frustumCulled,this.renderOrder=t.renderOrder,this.static=t.static,this.animations=t.animations.slice(),this.userData=JSON.parse(JSON.stringify(t.userData)),e===!0)for(let n=0;n<t.children.length;n++){let s=t.children[n];this.add(s.clone())}return this}dispose(){this.dispatchEvent({type:"dispose"})}};on.DEFAULT_UP=new F(0,1,0);on.DEFAULT_MATRIX_AUTO_UPDATE=!0;on.DEFAULT_MATRIX_WORLD_AUTO_UPDATE=!0;var se=class extends on{constructor(){super(),this.isGroup=!0,this.type="Group"}},pp={type:"move"},Rr=class{constructor(){this._targetRay=null,this._grip=null,this._hand=null}getHandSpace(){return this._hand===null&&(this._hand=new se,this._hand.matrixAutoUpdate=!1,this._hand.visible=!1,this._hand.joints={},this._hand.inputState={pinching:!1}),this._hand}getTargetRaySpace(){return this._targetRay===null&&(this._targetRay=new se,this._targetRay.matrixAutoUpdate=!1,this._targetRay.visible=!1,this._targetRay.hasLinearVelocity=!1,this._targetRay.linearVelocity=new F,this._targetRay.hasAngularVelocity=!1,this._targetRay.angularVelocity=new F),this._targetRay}getGripSpace(){return this._grip===null&&(this._grip=new se,this._grip.matrixAutoUpdate=!1,this._grip.visible=!1,this._grip.hasLinearVelocity=!1,this._grip.linearVelocity=new F,this._grip.hasAngularVelocity=!1,this._grip.angularVelocity=new F,this._grip.eventsEnabled=!1),this._grip}dispatchEvent(t){return this._targetRay!==null&&this._targetRay.dispatchEvent(t),this._grip!==null&&this._grip.dispatchEvent(t),this._hand!==null&&this._hand.dispatchEvent(t),this}connect(t){if(t&&t.hand){let e=this._hand;if(e)for(let n of t.hand.values())this._getHandJoint(e,n)}return this.dispatchEvent({type:"connected",data:t}),this}disconnect(t){return this.dispatchEvent({type:"disconnected",data:t}),this._targetRay!==null&&(this._targetRay.visible=!1),this._grip!==null&&(this._grip.visible=!1),this._hand!==null&&(this._hand.visible=!1),this}update(t,e,n){let s=null,r=null,a=null,l=this._targetRay,o=this._grip,c=this._hand;if(t&&e.session.visibilityState!=="visible-blurred"){if(c&&t.hand){a=!0;for(let M of t.hand.values()){let m=e.getJointPose(M,n),u=this._getHandJoint(c,M);m!==null&&(u.matrix.fromArray(m.transform.matrix),u.matrix.decompose(u.position,u.rotation,u.scale),u.matrixWorldNeedsUpdate=!0,u.jointRadius=m.radius),u.visible=m!==null}let h=c.joints["index-finger-tip"],f=c.joints["thumb-tip"],d=h.position.distanceTo(f.position),p=.02,x=.005;c.inputState.pinching&&d>p+x?(c.inputState.pinching=!1,this.dispatchEvent({type:"pinchend",handedness:t.handedness,target:this})):!c.inputState.pinching&&d<=p-x&&(c.inputState.pinching=!0,this.dispatchEvent({type:"pinchstart",handedness:t.handedness,target:this}))}else o!==null&&t.gripSpace&&(r=e.getPose(t.gripSpace,n),r!==null&&(o.matrix.fromArray(r.transform.matrix),o.matrix.decompose(o.position,o.rotation,o.scale),o.matrixWorldNeedsUpdate=!0,r.linearVelocity?(o.hasLinearVelocity=!0,o.linearVelocity.copy(r.linearVelocity)):o.hasLinearVelocity=!1,r.angularVelocity?(o.hasAngularVelocity=!0,o.angularVelocity.copy(r.angularVelocity)):o.hasAngularVelocity=!1,o.eventsEnabled&&o.dispatchEvent({type:"gripUpdated",data:t,target:this})));l!==null&&(s=e.getPose(t.targetRaySpace,n),s===null&&r!==null&&(s=r),s!==null&&(l.matrix.fromArray(s.transform.matrix),l.matrix.decompose(l.position,l.rotation,l.scale),l.matrixWorldNeedsUpdate=!0,s.linearVelocity?(l.hasLinearVelocity=!0,l.linearVelocity.copy(s.linearVelocity)):l.hasLinearVelocity=!1,s.angularVelocity?(l.hasAngularVelocity=!0,l.angularVelocity.copy(s.angularVelocity)):l.hasAngularVelocity=!1,this.dispatchEvent(pp)))}return l!==null&&(l.visible=s!==null),o!==null&&(o.visible=r!==null),c!==null&&(c.visible=a!==null),this}_getHandJoint(t,e){if(t.joints[e.jointName]===void 0){let n=new se;n.matrixAutoUpdate=!1,n.visible=!1,t.joints[e.jointName]=n,t.add(n)}return t.joints[e.jointName]}},fd={aliceblue:15792383,antiquewhite:16444375,aqua:65535,aquamarine:8388564,azure:15794175,beige:16119260,bisque:16770244,black:0,blanchedalmond:16772045,blue:255,blueviolet:9055202,brown:10824234,burlywood:14596231,cadetblue:6266528,chartreuse:8388352,chocolate:13789470,coral:16744272,cornflowerblue:6591981,cornsilk:16775388,crimson:14423100,cyan:65535,darkblue:139,darkcyan:35723,darkgoldenrod:12092939,darkgray:11119017,darkgreen:25600,darkgrey:11119017,darkkhaki:12433259,darkmagenta:9109643,darkolivegreen:5597999,darkorange:16747520,darkorchid:10040012,darkred:9109504,darksalmon:15308410,darkseagreen:9419919,darkslateblue:4734347,darkslategray:3100495,darkslategrey:3100495,darkturquoise:52945,darkviolet:9699539,deeppink:16716947,deepskyblue:49151,dimgray:6908265,dimgrey:6908265,dodgerblue:2003199,firebrick:11674146,floralwhite:16775920,forestgreen:2263842,fuchsia:16711935,gainsboro:14474460,ghostwhite:16316671,gold:16766720,goldenrod:14329120,gray:8421504,green:32768,greenyellow:11403055,grey:8421504,honeydew:15794160,hotpink:16738740,indianred:13458524,indigo:4915330,ivory:16777200,khaki:15787660,lavender:15132410,lavenderblush:16773365,lawngreen:8190976,lemonchiffon:16775885,lightblue:11393254,lightcoral:15761536,lightcyan:14745599,lightgoldenrodyellow:16448210,lightgray:13882323,lightgreen:9498256,lightgrey:13882323,lightpink:16758465,lightsalmon:16752762,lightseagreen:2142890,lightskyblue:8900346,lightslategray:7833753,lightslategrey:7833753,lightsteelblue:11584734,lightyellow:16777184,lime:65280,limegreen:3329330,linen:16445670,magenta:16711935,maroon:8388608,mediumaquamarine:6737322,mediumblue:205,mediumorchid:12211667,mediumpurple:9662683,mediumseagreen:3978097,mediumslateblue:8087790,mediumspringgreen:64154,mediumturquoise:4772300,mediumvioletred:13047173,midnightblue:1644912,mintcream:16121850,mistyrose:16770273,moccasin:16770229,navajowhite:16768685,navy:128,oldlace:16643558,olive:8421376,olivedrab:7048739,orange:16753920,orangered:16729344,orchid:14315734,palegoldenrod:15657130,palegreen:10025880,paleturquoise:11529966,palevioletred:14381203,papayawhip:16773077,peachpuff:16767673,peru:13468991,pink:16761035,plum:14524637,powderblue:11591910,purple:8388736,rebeccapurple:6697881,red:16711680,rosybrown:12357519,royalblue:4286945,saddlebrown:9127187,salmon:16416882,sandybrown:16032864,seagreen:3050327,seashell:16774638,sienna:10506797,silver:12632256,skyblue:8900331,slateblue:6970061,slategray:7372944,slategrey:7372944,snow:16775930,springgreen:65407,steelblue:4620980,tan:13808780,teal:32896,thistle:14204888,tomato:16737095,turquoise:4251856,violet:15631086,wheat:16113331,white:16777215,whitesmoke:16119285,yellow:16776960,yellowgreen:10145074},os={h:0,s:0,l:0},Ja={h:0,s:0,l:0};function mc(i,t,e){return e<0&&(e+=1),e>1&&(e-=1),e<1/6?i+(t-i)*6*e:e<1/2?t:e<2/3?i+(t-i)*6*(2/3-e):i}var $t=class{constructor(t,e,n){return this.isColor=!0,this.r=1,this.g=1,this.b=1,this.set(t,e,n)}set(t,e,n){if(e===void 0&&n===void 0){let s=t;s&&s.isColor?this.copy(s):typeof s=="number"?this.setHex(s):typeof s=="string"&&this.setStyle(s)}else this.setRGB(t,e,n);return this}setScalar(t){return this.r=t,this.g=t,this.b=t,this}setHex(t,e=Ge){return t=Math.floor(t),this.r=(t>>16&255)/255,this.g=(t>>8&255)/255,this.b=(t&255)/255,me.colorSpaceToWorking(this,e),this}setRGB(t,e,n,s=me.workingColorSpace){return this.r=t,this.g=e,this.b=n,me.colorSpaceToWorking(this,s),this}setHSL(t,e,n,s=me.workingColorSpace){if(t=lh(t,1),e=de(e,0,1),n=de(n,0,1),e===0)this.r=this.g=this.b=n;else{let r=n<=.5?n*(1+e):n+e-n*e,a=2*n-r;this.r=mc(a,r,t+1/3),this.g=mc(a,r,t),this.b=mc(a,r,t-1/3)}return me.colorSpaceToWorking(this,s),this}setStyle(t,e=Ge){function n(r){r!==void 0&&parseFloat(r)<1&&Zt("Color: Alpha component of "+t+" will be ignored.")}let s;if(s=/^(\w+)\(([^\)]*)\)/.exec(t)){let r,a=s[1],l=s[2];switch(a){case"rgb":case"rgba":if(r=/^\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(l))return n(r[4]),this.setRGB(Math.min(255,parseInt(r[1],10))/255,Math.min(255,parseInt(r[2],10))/255,Math.min(255,parseInt(r[3],10))/255,e);if(r=/^\s*(\d+)\%\s*,\s*(\d+)\%\s*,\s*(\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(l))return n(r[4]),this.setRGB(Math.min(100,parseInt(r[1],10))/100,Math.min(100,parseInt(r[2],10))/100,Math.min(100,parseInt(r[3],10))/100,e);break;case"hsl":case"hsla":if(r=/^\s*(\d*\.?\d+)\s*,\s*(\d*\.?\d+)\%\s*,\s*(\d*\.?\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(l))return n(r[4]),this.setHSL(parseFloat(r[1])/360,parseFloat(r[2])/100,parseFloat(r[3])/100,e);break;default:Zt("Color: Unknown color model "+t)}}else if(s=/^\#([A-Fa-f\d]+)$/.exec(t)){let r=s[1],a=r.length;if(a===3)return this.setRGB(parseInt(r.charAt(0),16)/15,parseInt(r.charAt(1),16)/15,parseInt(r.charAt(2),16)/15,e);if(a===6)return this.setHex(parseInt(r,16),e);Zt("Color: Invalid hex color "+t)}else if(t&&t.length>0)return this.setColorName(t,e);return this}setColorName(t,e=Ge){let n=fd[t.toLowerCase()];return n!==void 0?this.setHex(n,e):Zt("Color: Unknown color "+t),this}clone(){return new this.constructor(this.r,this.g,this.b)}copy(t){return this.r=t.r,this.g=t.g,this.b=t.b,this}copySRGBToLinear(t){return this.r=Xi(t.r),this.g=Xi(t.g),this.b=Xi(t.b),this}copyLinearToSRGB(t){return this.r=br(t.r),this.g=br(t.g),this.b=br(t.b),this}convertSRGBToLinear(){return this.copySRGBToLinear(this),this}convertLinearToSRGB(){return this.copyLinearToSRGB(this),this}getHex(t=Ge){return me.workingToColorSpace(_n.copy(this),t),Math.round(de(_n.r*255,0,255))*65536+Math.round(de(_n.g*255,0,255))*256+Math.round(de(_n.b*255,0,255))}getHexString(t=Ge){return("000000"+this.getHex(t).toString(16)).slice(-6)}getHSL(t,e=me.workingColorSpace){me.workingToColorSpace(_n.copy(this),e);let n=_n.r,s=_n.g,r=_n.b,a=Math.max(n,s,r),l=Math.min(n,s,r),o,c,h=(l+a)/2;if(l===a)o=0,c=0;else{let f=a-l;switch(c=h<=.5?f/(a+l):f/(2-a-l),a){case n:o=(s-r)/f+(s<r?6:0);break;case s:o=(r-n)/f+2;break;case r:o=(n-s)/f+4;break}o/=6}return t.h=o,t.s=c,t.l=h,t}getRGB(t,e=me.workingColorSpace){return me.workingToColorSpace(_n.copy(this),e),t.r=_n.r,t.g=_n.g,t.b=_n.b,t}getStyle(t=Ge){me.workingToColorSpace(_n.copy(this),t);let e=_n.r,n=_n.g,s=_n.b;return t!==Ge?`color(${t} ${e.toFixed(3)} ${n.toFixed(3)} ${s.toFixed(3)})`:`rgb(${Math.round(e*255)},${Math.round(n*255)},${Math.round(s*255)})`}offsetHSL(t,e,n){return this.getHSL(os),this.setHSL(os.h+t,os.s+e,os.l+n)}add(t){return this.r+=t.r,this.g+=t.g,this.b+=t.b,this}addColors(t,e){return this.r=t.r+e.r,this.g=t.g+e.g,this.b=t.b+e.b,this}addScalar(t){return this.r+=t,this.g+=t,this.b+=t,this}sub(t){return this.r=Math.max(0,this.r-t.r),this.g=Math.max(0,this.g-t.g),this.b=Math.max(0,this.b-t.b),this}multiply(t){return this.r*=t.r,this.g*=t.g,this.b*=t.b,this}multiplyScalar(t){return this.r*=t,this.g*=t,this.b*=t,this}lerp(t,e){return this.r+=(t.r-this.r)*e,this.g+=(t.g-this.g)*e,this.b+=(t.b-this.b)*e,this}lerpColors(t,e,n){return this.r=t.r+(e.r-t.r)*n,this.g=t.g+(e.g-t.g)*n,this.b=t.b+(e.b-t.b)*n,this}lerpHSL(t,e){this.getHSL(os),t.getHSL(Ja);let n=la(os.h,Ja.h,e),s=la(os.s,Ja.s,e),r=la(os.l,Ja.l,e);return this.setHSL(n,s,r),this}setFromVector3(t){return this.r=t.x,this.g=t.y,this.b=t.z,this}applyMatrix3(t){let e=this.r,n=this.g,s=this.b,r=t.elements;return this.r=r[0]*e+r[3]*n+r[6]*s,this.g=r[1]*e+r[4]*n+r[7]*s,this.b=r[2]*e+r[5]*n+r[8]*s,this}equals(t){return t.r===this.r&&t.g===this.g&&t.b===this.b}fromArray(t,e=0){return this.r=t[e],this.g=t[e+1],this.b=t[e+2],this}toArray(t=[],e=0){return t[e]=this.r,t[e+1]=this.g,t[e+2]=this.b,t}fromBufferAttribute(t,e){return this.r=t.getX(e),this.g=t.getY(e),this.b=t.getZ(e),this}toJSON(){return this.getHex()}*[Symbol.iterator](){yield this.r,yield this.g,yield this.b}},_n=new $t;$t.NAMES=fd;var Bs=class extends on{constructor(){super(),this.isScene=!0,this.type="Scene",this.background=null,this.environment=null,this.fog=null,this.backgroundBlurriness=0,this.backgroundIntensity=1,this.backgroundRotation=new Ln,this.environmentIntensity=1,this.environmentRotation=new Ln,this.overrideMaterial=null,typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}copy(t,e){return super.copy(t,e),t.background!==null&&(this.background=t.background.clone()),t.environment!==null&&(this.environment=t.environment.clone()),t.fog!==null&&(this.fog=t.fog.clone()),this.backgroundBlurriness=t.backgroundBlurriness,this.backgroundIntensity=t.backgroundIntensity,this.backgroundRotation.copy(t.backgroundRotation),this.environmentIntensity=t.environmentIntensity,this.environmentRotation.copy(t.environmentRotation),t.overrideMaterial!==null&&(this.overrideMaterial=t.overrideMaterial.clone()),this.matrixAutoUpdate=t.matrixAutoUpdate,this}toJSON(t){let e=super.toJSON(t);return this.fog!==null&&(e.object.fog=this.fog.toJSON()),e.object.backgroundBlurriness=this.backgroundBlurriness,e.object.backgroundIntensity=this.backgroundIntensity,e.object.backgroundRotation=this.backgroundRotation.toArray(),e.object.environmentIntensity=this.environmentIntensity,e.object.environmentRotation=this.environmentRotation.toArray(),e}},ai=new F,Hi=new F,gc=new F,Vi=new F,hr=new F,ur=new F,mu=new F,xc=new F,_c=new F,yc=new F,vc=new ke,bc=new ke,Mc=new ke,us=class i{constructor(t=new F,e=new F,n=new F){this.a=t,this.b=e,this.c=n}static getNormal(t,e,n,s){s.subVectors(n,e),ai.subVectors(t,e),s.cross(ai);let r=s.lengthSq();return r>0?s.multiplyScalar(1/Math.sqrt(r)):s.set(0,0,0)}static getBarycoord(t,e,n,s,r){ai.subVectors(s,e),Hi.subVectors(n,e),gc.subVectors(t,e);let a=ai.dot(ai),l=ai.dot(Hi),o=ai.dot(gc),c=Hi.dot(Hi),h=Hi.dot(gc),f=a*c-l*l;if(f===0)return r.set(0,0,0),null;let d=1/f,p=(c*o-l*h)*d,x=(a*h-l*o)*d;return r.set(1-p-x,x,p)}static containsPoint(t,e,n,s){return this.getBarycoord(t,e,n,s,Vi)===null?!1:Vi.x>=0&&Vi.y>=0&&Vi.x+Vi.y<=1}static getInterpolation(t,e,n,s,r,a,l,o){return this.getBarycoord(t,e,n,s,Vi)===null?(o.x=0,o.y=0,"z"in o&&(o.z=0),"w"in o&&(o.w=0),null):(o.setScalar(0),o.addScaledVector(r,Vi.x),o.addScaledVector(a,Vi.y),o.addScaledVector(l,Vi.z),o)}static getInterpolatedAttribute(t,e,n,s,r,a){return vc.setScalar(0),bc.setScalar(0),Mc.setScalar(0),vc.fromBufferAttribute(t,e),bc.fromBufferAttribute(t,n),Mc.fromBufferAttribute(t,s),a.setScalar(0),a.addScaledVector(vc,r.x),a.addScaledVector(bc,r.y),a.addScaledVector(Mc,r.z),a}static isFrontFacing(t,e,n,s){return ai.subVectors(n,e),Hi.subVectors(t,e),ai.cross(Hi).dot(s)<0}set(t,e,n){return this.a.copy(t),this.b.copy(e),this.c.copy(n),this}setFromPointsAndIndices(t,e,n,s){return this.a.copy(t[e]),this.b.copy(t[n]),this.c.copy(t[s]),this}setFromAttributeAndIndices(t,e,n,s){return this.a.fromBufferAttribute(t,e),this.b.fromBufferAttribute(t,n),this.c.fromBufferAttribute(t,s),this}clone(){return new this.constructor().copy(this)}copy(t){return this.a.copy(t.a),this.b.copy(t.b),this.c.copy(t.c),this}getArea(){return ai.subVectors(this.c,this.b),Hi.subVectors(this.a,this.b),ai.cross(Hi).length()*.5}getMidpoint(t){return t.addVectors(this.a,this.b).add(this.c).multiplyScalar(1/3)}getNormal(t){return i.getNormal(this.a,this.b,this.c,t)}getPlane(t){return t.setFromCoplanarPoints(this.a,this.b,this.c)}getBarycoord(t,e){return i.getBarycoord(t,this.a,this.b,this.c,e)}getInterpolation(t,e,n,s,r){return i.getInterpolation(t,this.a,this.b,this.c,e,n,s,r)}containsPoint(t){return i.containsPoint(t,this.a,this.b,this.c)}isFrontFacing(t){return i.isFrontFacing(this.a,this.b,this.c,t)}intersectsBox(t){return t.intersectsTriangle(this)}closestPointToPoint(t,e){let n=this.a,s=this.b,r=this.c,a,l;hr.subVectors(s,n),ur.subVectors(r,n),xc.subVectors(t,n);let o=hr.dot(xc),c=ur.dot(xc);if(o<=0&&c<=0)return e.copy(n);_c.subVectors(t,s);let h=hr.dot(_c),f=ur.dot(_c);if(h>=0&&f<=h)return e.copy(s);let d=o*f-h*c;if(d<=0&&o>=0&&h<=0)return a=o/(o-h),e.copy(n).addScaledVector(hr,a);yc.subVectors(t,r);let p=hr.dot(yc),x=ur.dot(yc);if(x>=0&&p<=x)return e.copy(r);let M=p*c-o*x;if(M<=0&&c>=0&&x<=0)return l=c/(c-x),e.copy(n).addScaledVector(ur,l);let m=h*x-p*f;if(m<=0&&f-h>=0&&p-x>=0)return mu.subVectors(r,s),l=(f-h)/(f-h+(p-x)),e.copy(s).addScaledVector(mu,l);let u=1/(m+M+d);return a=M*u,l=d*u,e.copy(n).addScaledVector(hr,a).addScaledVector(ur,l)}equals(t){return t.a.equals(this.a)&&t.b.equals(this.b)&&t.c.equals(this.c)}},wi=class{constructor(t=new F(1/0,1/0,1/0),e=new F(-1/0,-1/0,-1/0)){this.isBox3=!0,this.min=t,this.max=e}set(t,e){return this.min.copy(t),this.max.copy(e),this}setFromArray(t){this.makeEmpty();for(let e=0,n=t.length;e<n;e+=3)this.expandByPoint(oi.fromArray(t,e));return this}setFromBufferAttribute(t){this.makeEmpty();for(let e=0,n=t.count;e<n;e++)this.expandByPoint(oi.fromBufferAttribute(t,e));return this}setFromPoints(t){this.makeEmpty();for(let e=0,n=t.length;e<n;e++)this.expandByPoint(t[e]);return this}setFromCenterAndSize(t,e){let n=oi.copy(e).multiplyScalar(.5);return this.min.copy(t).sub(n),this.max.copy(t).add(n),this}setFromObject(t,e=!1){return this.makeEmpty(),this.expandByObject(t,e)}clone(){return new this.constructor().copy(this)}copy(t){return this.min.copy(t.min),this.max.copy(t.max),this}makeEmpty(){return this.min.x=this.min.y=this.min.z=1/0,this.max.x=this.max.y=this.max.z=-1/0,this}isEmpty(){return this.max.x<this.min.x||this.max.y<this.min.y||this.max.z<this.min.z}getCenter(t){return this.isEmpty()?t.set(0,0,0):t.addVectors(this.min,this.max).multiplyScalar(.5)}getSize(t){return this.isEmpty()?t.set(0,0,0):t.subVectors(this.max,this.min)}expandByPoint(t){return this.min.min(t),this.max.max(t),this}expandByVector(t){return this.min.sub(t),this.max.add(t),this}expandByScalar(t){return this.min.addScalar(-t),this.max.addScalar(t),this}expandByObject(t,e=!1){t.updateWorldMatrix(!1,!1);let n=t.geometry;if(n!==void 0){let r=n.getAttribute("position");if(e===!0&&r!==void 0&&t.isInstancedMesh!==!0)for(let a=0,l=r.count;a<l;a++)t.isMesh===!0?t.getVertexPosition(a,oi):oi.fromBufferAttribute(r,a),oi.applyMatrix4(t.matrixWorld),this.expandByPoint(oi);else t.boundingBox!==void 0?(t.boundingBox===null&&t.computeBoundingBox(),ja.copy(t.boundingBox)):(n.boundingBox===null&&n.computeBoundingBox(),ja.copy(n.boundingBox)),ja.applyMatrix4(t.matrixWorld),this.union(ja)}let s=t.children;for(let r=0,a=s.length;r<a;r++)this.expandByObject(s[r],e);return this}containsPoint(t){return t.x>=this.min.x&&t.x<=this.max.x&&t.y>=this.min.y&&t.y<=this.max.y&&t.z>=this.min.z&&t.z<=this.max.z}containsBox(t){return this.min.x<=t.min.x&&t.max.x<=this.max.x&&this.min.y<=t.min.y&&t.max.y<=this.max.y&&this.min.z<=t.min.z&&t.max.z<=this.max.z}getParameter(t,e){return e.set((t.x-this.min.x)/(this.max.x-this.min.x),(t.y-this.min.y)/(this.max.y-this.min.y),(t.z-this.min.z)/(this.max.z-this.min.z))}intersectsBox(t){return t.max.x>=this.min.x&&t.min.x<=this.max.x&&t.max.y>=this.min.y&&t.min.y<=this.max.y&&t.max.z>=this.min.z&&t.min.z<=this.max.z}intersectsSphere(t){return this.clampPoint(t.center,oi),oi.distanceToSquared(t.center)<=t.radius*t.radius}intersectsPlane(t){let e,n;return t.normal.x>0?(e=t.normal.x*this.min.x,n=t.normal.x*this.max.x):(e=t.normal.x*this.max.x,n=t.normal.x*this.min.x),t.normal.y>0?(e+=t.normal.y*this.min.y,n+=t.normal.y*this.max.y):(e+=t.normal.y*this.max.y,n+=t.normal.y*this.min.y),t.normal.z>0?(e+=t.normal.z*this.min.z,n+=t.normal.z*this.max.z):(e+=t.normal.z*this.max.z,n+=t.normal.z*this.min.z),e<=-t.constant&&n>=-t.constant}intersectsTriangle(t){if(this.isEmpty())return!1;this.getCenter(na),Qa.subVectors(this.max,na),dr.subVectors(t.a,na),fr.subVectors(t.b,na),pr.subVectors(t.c,na),ls.subVectors(fr,dr),cs.subVectors(pr,fr),Ds.subVectors(dr,pr);let e=[0,-ls.z,ls.y,0,-cs.z,cs.y,0,-Ds.z,Ds.y,ls.z,0,-ls.x,cs.z,0,-cs.x,Ds.z,0,-Ds.x,-ls.y,ls.x,0,-cs.y,cs.x,0,-Ds.y,Ds.x,0];return!Sc(e,dr,fr,pr,Qa)||(e=[1,0,0,0,1,0,0,0,1],!Sc(e,dr,fr,pr,Qa))?!1:(to.crossVectors(ls,cs),e=[to.x,to.y,to.z],Sc(e,dr,fr,pr,Qa))}clampPoint(t,e){return e.copy(t).clamp(this.min,this.max)}distanceToPoint(t){return this.clampPoint(t,oi).distanceTo(t)}getBoundingSphere(t){return this.isEmpty()?t.makeEmpty():(this.getCenter(t.center),t.radius=this.getSize(oi).length()*.5),t}intersect(t){return this.min.max(t.min),this.max.min(t.max),this.isEmpty()&&this.makeEmpty(),this}union(t){return this.min.min(t.min),this.max.max(t.max),this}applyMatrix4(t){return this.isEmpty()?this:(Gi[0].set(this.min.x,this.min.y,this.min.z).applyMatrix4(t),Gi[1].set(this.min.x,this.min.y,this.max.z).applyMatrix4(t),Gi[2].set(this.min.x,this.max.y,this.min.z).applyMatrix4(t),Gi[3].set(this.min.x,this.max.y,this.max.z).applyMatrix4(t),Gi[4].set(this.max.x,this.min.y,this.min.z).applyMatrix4(t),Gi[5].set(this.max.x,this.min.y,this.max.z).applyMatrix4(t),Gi[6].set(this.max.x,this.max.y,this.min.z).applyMatrix4(t),Gi[7].set(this.max.x,this.max.y,this.max.z).applyMatrix4(t),this.setFromPoints(Gi),this)}translate(t){return this.min.add(t),this.max.add(t),this}equals(t){return t.min.equals(this.min)&&t.max.equals(this.max)}toJSON(){return{min:this.min.toArray(),max:this.max.toArray()}}fromJSON(t){return this.min.fromArray(t.min),this.max.fromArray(t.max),this}},Gi=[new F,new F,new F,new F,new F,new F,new F,new F],oi=new F,ja=new wi,dr=new F,fr=new F,pr=new F,ls=new F,cs=new F,Ds=new F,na=new F,Qa=new F,to=new F,Ns=new F;function Sc(i,t,e,n,s){for(let r=0,a=i.length-3;r<=a;r+=3){Ns.fromArray(i,r);let l=s.x*Math.abs(Ns.x)+s.y*Math.abs(Ns.y)+s.z*Math.abs(Ns.z),o=t.dot(Ns),c=e.dot(Ns),h=n.dot(Ns);if(Math.max(-Math.max(o,c,h),Math.min(o,c,h))>l)return!1}return!0}var Ze=new F,eo=new Xt,mp=0,pn=class extends ci{constructor(t,e,n=!1){if(super(),Array.isArray(t))throw new TypeError("THREE.BufferAttribute: array should be a Typed Array.");this.isBufferAttribute=!0,Object.defineProperty(this,"id",{value:mp++}),this.name="",this.array=t,this.itemSize=e,this.count=t!==void 0?t.length/e:0,this.normalized=n,this.usage=ld,this.updateRanges=[],this.gpuType=Zn,this.version=0}onUploadCallback(){}set needsUpdate(t){t===!0&&this.version++}setUsage(t){return this.usage=t,this}addUpdateRange(t,e){this.updateRanges.push({start:t,count:e})}clearUpdateRanges(){this.updateRanges.length=0}copy(t){return this.name=t.name,this.array=new t.array.constructor(t.array),this.itemSize=t.itemSize,this.count=t.count,this.normalized=t.normalized,this.usage=t.usage,this.gpuType=t.gpuType,this}copyAt(t,e,n){t*=this.itemSize,n*=e.itemSize;for(let s=0,r=this.itemSize;s<r;s++)this.array[t+s]=e.array[n+s];return this}copyArray(t){return this.array.set(t),this}applyMatrix3(t){if(this.itemSize===2)for(let e=0,n=this.count;e<n;e++)eo.fromBufferAttribute(this,e),eo.applyMatrix3(t),this.setXY(e,eo.x,eo.y);else if(this.itemSize===3)for(let e=0,n=this.count;e<n;e++)Ze.fromBufferAttribute(this,e),Ze.applyMatrix3(t),this.setXYZ(e,Ze.x,Ze.y,Ze.z);return this}applyMatrix4(t){for(let e=0,n=this.count;e<n;e++)Ze.fromBufferAttribute(this,e),Ze.applyMatrix4(t),this.setXYZ(e,Ze.x,Ze.y,Ze.z);return this}applyNormalMatrix(t){for(let e=0,n=this.count;e<n;e++)Ze.fromBufferAttribute(this,e),Ze.applyNormalMatrix(t),this.setXYZ(e,Ze.x,Ze.y,Ze.z);return this}transformDirection(t){for(let e=0,n=this.count;e<n;e++)Ze.fromBufferAttribute(this,e),Ze.transformDirection(t),this.setXYZ(e,Ze.x,Ze.y,Ze.z);return this}set(t,e=0){return this.array.set(t,e),this}getComponent(t,e){let n=this.array[t*this.itemSize+e];return this.normalized&&(n=vr(n,this.array)),n}setComponent(t,e,n){return this.normalized&&(n=En(n,this.array)),this.array[t*this.itemSize+e]=n,this}getX(t){let e=this.array[t*this.itemSize];return this.normalized&&(e=vr(e,this.array)),e}setX(t,e){return this.normalized&&(e=En(e,this.array)),this.array[t*this.itemSize]=e,this}getY(t){let e=this.array[t*this.itemSize+1];return this.normalized&&(e=vr(e,this.array)),e}setY(t,e){return this.normalized&&(e=En(e,this.array)),this.array[t*this.itemSize+1]=e,this}getZ(t){let e=this.array[t*this.itemSize+2];return this.normalized&&(e=vr(e,this.array)),e}setZ(t,e){return this.normalized&&(e=En(e,this.array)),this.array[t*this.itemSize+2]=e,this}getW(t){let e=this.array[t*this.itemSize+3];return this.normalized&&(e=vr(e,this.array)),e}setW(t,e){return this.normalized&&(e=En(e,this.array)),this.array[t*this.itemSize+3]=e,this}setXY(t,e,n){return t*=this.itemSize,this.normalized&&(e=En(e,this.array),n=En(n,this.array)),this.array[t+0]=e,this.array[t+1]=n,this}setXYZ(t,e,n,s){return t*=this.itemSize,this.normalized&&(e=En(e,this.array),n=En(n,this.array),s=En(s,this.array)),this.array[t+0]=e,this.array[t+1]=n,this.array[t+2]=s,this}setXYZW(t,e,n,s,r){return t*=this.itemSize,this.normalized&&(e=En(e,this.array),n=En(n,this.array),s=En(s,this.array),r=En(r,this.array)),this.array[t+0]=e,this.array[t+1]=n,this.array[t+2]=s,this.array[t+3]=r,this}onUpload(t){return this.onUploadCallback=t,this}clone(){return new this.constructor(this.array,this.itemSize).copy(this)}toJSON(){let t={itemSize:this.itemSize,type:this.array.constructor.name,array:Array.from(this.array),normalized:this.normalized};return t.name=this.name,t.usage=this.usage,t.gpuType=this.gpuType,t}dispose(){this.dispatchEvent({type:"dispose"})}};var pa=class extends pn{constructor(t,e,n){super(new Uint16Array(t),e,n)}};var ma=class extends pn{constructor(t,e,n){super(new Uint32Array(t),e,n)}};var Ee=class extends pn{constructor(t,e,n){super(new Float32Array(t),e,n)}},gp=new wi,ia=new F,Ec=new F,ds=class{constructor(t=new F,e=-1){this.isSphere=!0,this.center=t,this.radius=e}set(t,e){return this.center.copy(t),this.radius=e,this}setFromPoints(t,e){let n=this.center;e!==void 0?n.copy(e):gp.setFromPoints(t).getCenter(n);let s=0;for(let r=0,a=t.length;r<a;r++)s=Math.max(s,n.distanceToSquared(t[r]));return this.radius=Math.sqrt(s),this}copy(t){return this.center.copy(t.center),this.radius=t.radius,this}isEmpty(){return this.radius<0}makeEmpty(){return this.center.set(0,0,0),this.radius=-1,this}containsPoint(t){return t.distanceToSquared(this.center)<=this.radius*this.radius}distanceToPoint(t){return t.distanceTo(this.center)-this.radius}intersectsSphere(t){let e=this.radius+t.radius;return t.center.distanceToSquared(this.center)<=e*e}intersectsBox(t){return t.intersectsSphere(this)}intersectsPlane(t){return Math.abs(t.distanceToPoint(this.center))<=this.radius}clampPoint(t,e){let n=this.center.distanceToSquared(t);return e.copy(t),n>this.radius*this.radius&&(e.sub(this.center).normalize(),e.multiplyScalar(this.radius).add(this.center)),e}getBoundingBox(t){return this.isEmpty()?(t.makeEmpty(),t):(t.set(this.center,this.center),t.expandByScalar(this.radius),t)}applyMatrix4(t){return this.center.applyMatrix4(t),this.radius=this.radius*t.getMaxScaleOnAxis(),this}translate(t){return this.center.add(t),this}expandByPoint(t){if(this.isEmpty())return this.center.copy(t),this.radius=0,this;ia.subVectors(t,this.center);let e=ia.lengthSq();if(e>this.radius*this.radius){let n=Math.sqrt(e),s=(n-this.radius)*.5;this.center.addScaledVector(ia,s/n),this.radius+=s}return this}union(t){return t.isEmpty()?this:this.isEmpty()?(this.copy(t),this):(this.center.equals(t.center)===!0?this.radius=Math.max(this.radius,t.radius):(Ec.subVectors(t.center,this.center).setLength(t.radius),this.expandByPoint(ia.copy(t.center).add(Ec)),this.expandByPoint(ia.copy(t.center).sub(Ec))),this)}equals(t){return t.center.equals(this.center)&&t.radius===this.radius}clone(){return new this.constructor().copy(this)}toJSON(){return{radius:this.radius,center:this.center.toArray()}}fromJSON(t){return this.radius=t.radius,this.center.fromArray(t.center),this}},xp=0,Yn=new ge,wc=new on,mr=new F,kn=new wi,sa=new wi,rn=new F,je=class i extends ci{constructor(){super(),this.isBufferGeometry=!0,Object.defineProperty(this,"id",{value:xp++}),this.uuid=Or(),this.name="",this.type="BufferGeometry",this.index=null,this.indirect=null,this.indirectOffset=0,this.attributes={},this.morphAttributes={},this.morphTargetsRelative=!1,this.groups=[],this.boundingBox=null,this.boundingSphere=null,this.drawRange={start:0,count:1/0},this.userData={},this._transformed=!1}getIndex(){return this.index}setIndex(t){return Array.isArray(t)?this.index=new(Hf(t)?ma:pa)(t,1):this.index=t,this}setIndirect(t,e=0){return this.indirect=t,this.indirectOffset=e,this}getIndirect(){return this.indirect}getAttribute(t){return this.attributes[t]}setAttribute(t,e){return this.attributes[t]=e,this}deleteAttribute(t){return delete this.attributes[t],this}hasAttribute(t){return this.attributes[t]!==void 0}addGroup(t,e,n=0){this.groups.push({start:t,count:e,materialIndex:n})}clearGroups(){this.groups=[]}setDrawRange(t,e){this.drawRange.start=t,this.drawRange.count=e}applyMatrix4(t){let e=this.attributes.position;e!==void 0&&(e.applyMatrix4(t),e.needsUpdate=!0);let n=this.attributes.normal;if(n!==void 0){let r=new Qt().getNormalMatrix(t);n.applyNormalMatrix(r),n.needsUpdate=!0}let s=this.attributes.tangent;return s!==void 0&&(s.transformDirection(t),s.needsUpdate=!0),this.boundingBox!==null&&this.computeBoundingBox(),this.boundingSphere!==null&&this.computeBoundingSphere(),this._transformed=!0,this}applyQuaternion(t){return Yn.makeRotationFromQuaternion(t),this.applyMatrix4(Yn),this}rotateX(t){return Yn.makeRotationX(t),this.applyMatrix4(Yn),this}rotateY(t){return Yn.makeRotationY(t),this.applyMatrix4(Yn),this}rotateZ(t){return Yn.makeRotationZ(t),this.applyMatrix4(Yn),this}translate(t,e,n){return Yn.makeTranslation(t,e,n),this.applyMatrix4(Yn),this}scale(t,e,n){return Yn.makeScale(t,e,n),this.applyMatrix4(Yn),this}lookAt(t){return wc.lookAt(t),wc.updateMatrix(),this.applyMatrix4(wc.matrix),this}center(){return this.computeBoundingBox(),this.boundingBox.getCenter(mr).negate(),this.translate(mr.x,mr.y,mr.z),this}setFromPoints(t){let e=this.getAttribute("position");if(e===void 0){let n=[];for(let s=0,r=t.length;s<r;s++){let a=t[s];n.push(a.x,a.y,a.z||0)}this.setAttribute("position",new Ee(n,3))}else{let n=Math.min(t.length,e.count);for(let s=0;s<n;s++){let r=t[s];e.setXYZ(s,r.x,r.y,r.z||0)}t.length>e.count&&Zt("BufferGeometry: Buffer size too small for points data. Use .dispose() and create a new geometry."),e.needsUpdate=!0}return this}computeBoundingBox(){this.boundingBox===null&&(this.boundingBox=new wi);let t=this.attributes.position,e=this.morphAttributes.position;if(t&&t.isGLBufferAttribute){Kt("BufferGeometry.computeBoundingBox(): GLBufferAttribute requires a manual bounding box.",this),this.boundingBox.set(new F(-1/0,-1/0,-1/0),new F(1/0,1/0,1/0));return}if(t!==void 0){if(this.boundingBox.setFromBufferAttribute(t),e)for(let n=0,s=e.length;n<s;n++){let r=e[n];kn.setFromBufferAttribute(r),this.morphTargetsRelative?(rn.addVectors(this.boundingBox.min,kn.min),this.boundingBox.expandByPoint(rn),rn.addVectors(this.boundingBox.max,kn.max),this.boundingBox.expandByPoint(rn)):(this.boundingBox.expandByPoint(kn.min),this.boundingBox.expandByPoint(kn.max))}}else this.boundingBox.makeEmpty();(isNaN(this.boundingBox.min.x)||isNaN(this.boundingBox.min.y)||isNaN(this.boundingBox.min.z))&&Kt('BufferGeometry.computeBoundingBox(): Computed min/max have NaN values. The "position" attribute is likely to have NaN values.',this)}computeBoundingSphere(){this.boundingSphere===null&&(this.boundingSphere=new ds);let t=this.attributes.position,e=this.morphAttributes.position;if(t&&t.isGLBufferAttribute){Kt("BufferGeometry.computeBoundingSphere(): GLBufferAttribute requires a manual bounding sphere.",this),this.boundingSphere.set(new F,1/0);return}if(t){let n=this.boundingSphere.center;if(kn.setFromBufferAttribute(t),e)for(let r=0,a=e.length;r<a;r++){let l=e[r];sa.setFromBufferAttribute(l),this.morphTargetsRelative?(rn.addVectors(kn.min,sa.min),kn.expandByPoint(rn),rn.addVectors(kn.max,sa.max),kn.expandByPoint(rn)):(kn.expandByPoint(sa.min),kn.expandByPoint(sa.max))}kn.getCenter(n);let s=0;for(let r=0,a=t.count;r<a;r++)rn.fromBufferAttribute(t,r),s=Math.max(s,n.distanceToSquared(rn));if(e)for(let r=0,a=e.length;r<a;r++){let l=e[r],o=this.morphTargetsRelative;for(let c=0,h=l.count;c<h;c++)rn.fromBufferAttribute(l,c),o&&(mr.fromBufferAttribute(t,c),rn.add(mr)),s=Math.max(s,n.distanceToSquared(rn))}this.boundingSphere.radius=Math.sqrt(s),isNaN(this.boundingSphere.radius)&&Kt('BufferGeometry.computeBoundingSphere(): Computed radius is NaN. The "position" attribute is likely to have NaN values.',this)}}computeTangents(){let t=this.index,e=this.attributes;if(t===null||e.position===void 0||e.normal===void 0||e.uv===void 0){Kt("BufferGeometry: .computeTangents() failed. Missing required attributes (index, position, normal or uv)");return}let n=e.position,s=e.normal,r=e.uv,a=this.getAttribute("tangent");(a===void 0||a.count!==n.count)&&(a=new pn(new Float32Array(4*n.count),4),this.setAttribute("tangent",a));let l=[],o=[];for(let g=0;g<n.count;g++)l[g]=new F,o[g]=new F;let c=new F,h=new F,f=new F,d=new Xt,p=new Xt,x=new Xt,M=new F,m=new F;function u(g,w,T){c.fromBufferAttribute(n,g),h.fromBufferAttribute(n,w),f.fromBufferAttribute(n,T),d.fromBufferAttribute(r,g),p.fromBufferAttribute(r,w),x.fromBufferAttribute(r,T),h.sub(c),f.sub(c),p.sub(d),x.sub(d);let C=1/(p.x*x.y-x.x*p.y);isFinite(C)&&(M.copy(h).multiplyScalar(x.y).addScaledVector(f,-p.y).multiplyScalar(C),m.copy(f).multiplyScalar(p.x).addScaledVector(h,-x.x).multiplyScalar(C),l[g].add(M),l[w].add(M),l[T].add(M),o[g].add(m),o[w].add(m),o[T].add(m))}let b=this.groups;b.length===0&&(b=[{start:0,count:t.count}]);for(let g=0,w=b.length;g<w;++g){let T=b[g],C=T.start,D=T.count;for(let V=C,U=C+D;V<U;V+=3)u(t.getX(V+0),t.getX(V+1),t.getX(V+2))}let A=new F,v=new F,S=new F,E=new F;function R(g){S.fromBufferAttribute(s,g),E.copy(S);let w=l[g];A.copy(w),A.sub(S.multiplyScalar(S.dot(w))).normalize(),v.crossVectors(E,w);let C=v.dot(o[g])<0?-1:1;a.setXYZW(g,A.x,A.y,A.z,C)}for(let g=0,w=b.length;g<w;++g){let T=b[g],C=T.start,D=T.count;for(let V=C,U=C+D;V<U;V+=3)R(t.getX(V+0)),R(t.getX(V+1)),R(t.getX(V+2))}this._transformed=!0}computeVertexNormals(){let t=this.index,e=this.getAttribute("position");if(e!==void 0){let n=this.getAttribute("normal");if(n===void 0||n.count!==e.count)n=new pn(new Float32Array(e.count*3),3),this.setAttribute("normal",n);else for(let d=0,p=n.count;d<p;d++)n.setXYZ(d,0,0,0);let s=new F,r=new F,a=new F,l=new F,o=new F,c=new F,h=new F,f=new F;if(t)for(let d=0,p=t.count;d<p;d+=3){let x=t.getX(d+0),M=t.getX(d+1),m=t.getX(d+2);s.fromBufferAttribute(e,x),r.fromBufferAttribute(e,M),a.fromBufferAttribute(e,m),h.subVectors(a,r),f.subVectors(s,r),h.cross(f),l.fromBufferAttribute(n,x),o.fromBufferAttribute(n,M),c.fromBufferAttribute(n,m),l.add(h),o.add(h),c.add(h),n.setXYZ(x,l.x,l.y,l.z),n.setXYZ(M,o.x,o.y,o.z),n.setXYZ(m,c.x,c.y,c.z)}else for(let d=0,p=e.count;d<p;d+=3)s.fromBufferAttribute(e,d+0),r.fromBufferAttribute(e,d+1),a.fromBufferAttribute(e,d+2),h.subVectors(a,r),f.subVectors(s,r),h.cross(f),n.setXYZ(d+0,h.x,h.y,h.z),n.setXYZ(d+1,h.x,h.y,h.z),n.setXYZ(d+2,h.x,h.y,h.z);this.normalizeNormals(),n.needsUpdate=!0}}normalizeNormals(){let t=this.attributes.normal;for(let e=0,n=t.count;e<n;e++)rn.fromBufferAttribute(t,e),rn.normalize(),t.setXYZ(e,rn.x,rn.y,rn.z)}toNonIndexed(){function t(l,o){let c=l.array,h=l.itemSize,f=l.normalized,d=new c.constructor(o.length*h),p=0,x=0;for(let M=0,m=o.length;M<m;M++){l.isInterleavedBufferAttribute?p=o[M]*l.data.stride+l.offset:p=o[M]*h;for(let u=0;u<h;u++)d[x++]=c[p++]}return new pn(d,h,f)}if(this.index===null)return Zt("BufferGeometry.toNonIndexed(): BufferGeometry is already non-indexed."),this;let e=new i,n=this.index.array,s=this.attributes;for(let l in s){let o=s[l],c=t(o,n);e.setAttribute(l,c)}let r=this.morphAttributes;for(let l in r){let o=[],c=r[l];for(let h=0,f=c.length;h<f;h++){let d=c[h],p=t(d,n);o.push(p)}e.morphAttributes[l]=o}e.morphTargetsRelative=this.morphTargetsRelative;let a=this.groups;for(let l=0,o=a.length;l<o;l++){let c=a[l];e.addGroup(c.start,c.count,c.materialIndex)}return e}toJSON(){let t={metadata:{version:4.7,type:"BufferGeometry",generator:"BufferGeometry.toJSON"}};if(t.uuid=this.uuid,t.type=this.parameters!==void 0&&this._transformed===!0?"BufferGeometry":this.type,t.name=this.name,Object.keys(this.userData).length>0&&(t.userData=this.userData),this.parameters!==void 0&&this._transformed!==!0){let o=this.parameters;for(let c in o)o[c]!==void 0&&(t[c]=o[c]);return t}t.data={attributes:{}};let e=this.index;e!==null&&(t.data.index={type:e.array.constructor.name,array:Array.prototype.slice.call(e.array)});let n=this.attributes;for(let o in n){let c=n[o];t.data.attributes[o]=c.toJSON(t.data)}let s={},r=!1;for(let o in this.morphAttributes){let c=this.morphAttributes[o],h=[];for(let f=0,d=c.length;f<d;f++){let p=c[f];h.push(p.toJSON(t.data))}h.length>0&&(s[o]=h,r=!0)}r&&(t.data.morphAttributes=s,t.data.morphTargetsRelative=this.morphTargetsRelative);let a=this.groups;a.length>0&&(t.data.groups=JSON.parse(JSON.stringify(a)));let l=this.boundingSphere;return l!==null&&(t.data.boundingSphere=l.toJSON()),t}clone(){return new this.constructor().copy(this)}copy(t){this.index=null,this.attributes={},this.morphAttributes={},this.groups=[],this.boundingBox=null,this.boundingSphere=null;let e={};this.name=t.name;let n=t.index;n!==null&&this.setIndex(n.clone());let s=t.attributes;for(let c in s){let h=s[c];this.setAttribute(c,h.clone(e))}let r=t.morphAttributes;for(let c in r){let h=[],f=r[c];for(let d=0,p=f.length;d<p;d++)h.push(f[d].clone(e));this.morphAttributes[c]=h}this.morphTargetsRelative=t.morphTargetsRelative;let a=t.groups;for(let c=0,h=a.length;c<h;c++){let f=a[c];this.addGroup(f.start,f.count,f.materialIndex)}let l=t.boundingBox;l!==null&&(this.boundingBox=l.clone());let o=t.boundingSphere;return o!==null&&(this.boundingSphere=o.clone()),this.drawRange.start=t.drawRange.start,this.drawRange.count=t.drawRange.count,this.userData=t.userData,this._transformed=t._transformed,this}dispose(){this.dispatchEvent({type:"dispose"})}};var Tc=new F,_p=new F,yp=new Qt,Hn=class{constructor(t=new F(1,0,0),e=0){this.isPlane=!0,this.normal=t,this.constant=e}set(t,e){return this.normal.copy(t),this.constant=e,this}setComponents(t,e,n,s){return this.normal.set(t,e,n),this.constant=s,this}setFromNormalAndCoplanarPoint(t,e){return this.normal.copy(t),this.constant=-e.dot(this.normal),this}setFromCoplanarPoints(t,e,n){let s=Tc.subVectors(n,e).cross(_p.subVectors(t,e)).normalize();return this.setFromNormalAndCoplanarPoint(s,t),this}copy(t){return this.normal.copy(t.normal),this.constant=t.constant,this}normalize(){let t=1/this.normal.length();return this.normal.multiplyScalar(t),this.constant*=t,this}negate(){return this.constant*=-1,this.normal.negate(),this}distanceToPoint(t){return this.normal.dot(t)+this.constant}distanceToSphere(t){return this.distanceToPoint(t.center)-t.radius}projectPoint(t,e){return e.copy(t).addScaledVector(this.normal,-this.distanceToPoint(t))}intersectLine(t,e,n=!0){let s=t.delta(Tc),r=this.normal.dot(s);if(r===0)return this.distanceToPoint(t.start)===0?e.copy(t.start):null;let a=-(t.start.dot(this.normal)+this.constant)/r;return n===!0&&(a<0||a>1)?null:e.copy(t.start).addScaledVector(s,a)}intersectsLine(t){let e=this.distanceToPoint(t.start),n=this.distanceToPoint(t.end);return e<0&&n>0||n<0&&e>0}intersectsBox(t){return t.intersectsPlane(this)}intersectsSphere(t){return t.intersectsPlane(this)}coplanarPoint(t){return t.copy(this.normal).multiplyScalar(-this.constant)}applyMatrix4(t,e){let n=e||yp.getNormalMatrix(t),s=this.coplanarPoint(Tc).applyMatrix4(t),r=this.normal.applyMatrix3(n).normalize();return this.constant=-s.dot(r),this}translate(t){return this.constant-=t.dot(this.normal),this}equals(t){return t.normal.equals(this.normal)&&t.constant===this.constant}clone(){return new this.constructor().copy(this)}toJSON(){return{normal:this.normal.toArray(),constant:this.constant}}fromJSON(t){return this.normal.fromArray(t.normal),this.constant=t.constant,this}},vp=0,fs=class extends ci{constructor(){super(),this.isMaterial=!0,Object.defineProperty(this,"id",{value:vp++}),this.uuid=Or(),this.name="",this.type="Material",this.blending=Nr,this.side=vs,this.vertexColors=!1,this.opacity=1,this.transparent=!1,this.alphaHash=!1,this.blendSrc=Wc,this.blendDst=Xc,this.blendEquation=Xs,this.blendSrcAlpha=null,this.blendDstAlpha=null,this.blendEquationAlpha=null,this.blendColor=new $t(0,0,0),this.blendAlpha=0,this.depthFunc=Mr,this.depthTest=!0,this.depthWrite=!0,this.stencilWriteMask=255,this.stencilFunc=ed,this.stencilRef=0,this.stencilFuncMask=255,this.stencilFail=xo,this.stencilZFail=xo,this.stencilZPass=xo,this.stencilWrite=!1,this.clippingPlanes=null,this.clipIntersection=!1,this.clipShadows=!1,this.shadowSide=null,this.colorWrite=!0,this.precision=null,this.polygonOffset=!1,this.polygonOffsetFactor=0,this.polygonOffsetUnits=0,this.dithering=!1,this.alphaToCoverage=!1,this.premultipliedAlpha=!1,this.forceSinglePass=!1,this.allowOverride=!0,this.visible=!0,this.toneMapped=!0,this.userData={},this.version=0,this._alphaTest=0}get alphaTest(){return this._alphaTest}set alphaTest(t){this._alphaTest>0!=t>0&&this.version++,this._alphaTest=t}onBeforeRender(){}onBeforeCompile(){}customProgramCacheKey(){return this.onBeforeCompile.toString()}setValues(t){if(t!==void 0)for(let e in t){let n=t[e];if(n===void 0){Zt(`Material: parameter '${e}' has value of undefined.`);continue}let s=this[e];if(s===void 0){Zt(`Material: '${e}' is not a property of THREE.${this.type}.`);continue}s&&s.isColor?s.set(n):s&&s.isVector2&&n&&n.isVector2||s&&s.isEuler&&n&&n.isEuler||s&&s.isVector3&&n&&n.isVector3?s.copy(n):this[e]=n}}toJSON(t){let e=t===void 0||typeof t=="string";e&&(t={textures:{},images:{}});let n={metadata:{version:4.7,type:"Material",generator:"Material.toJSON"}};n.uuid=this.uuid,n.type=this.type,n.blending=this.blending,n.side=this.side,n.shadowSide=this.shadowSide,n.vertexColors=this.vertexColors,n.opacity=this.opacity,n.transparent=this.transparent,n.blendSrc=this.blendSrc,n.blendDst=this.blendDst,n.blendEquation=this.blendEquation,n.blendSrcAlpha=this.blendSrcAlpha,n.blendDstAlpha=this.blendDstAlpha,n.blendEquationAlpha=this.blendEquationAlpha,n.blendColor=this.blendColor.getHex(),n.blendAlpha=this.blendAlpha,n.depthFunc=this.depthFunc,n.depthTest=this.depthTest,n.depthWrite=this.depthWrite,n.colorWrite=this.colorWrite,n.clipIntersection=this.clipIntersection,n.clipShadows=this.clipShadows,n.stencilWriteMask=this.stencilWriteMask,n.stencilFunc=this.stencilFunc,n.stencilRef=this.stencilRef,n.stencilFuncMask=this.stencilFuncMask,n.stencilFail=this.stencilFail,n.stencilZFail=this.stencilZFail,n.stencilZPass=this.stencilZPass,n.stencilWrite=this.stencilWrite,n.polygonOffset=this.polygonOffset,n.polygonOffsetFactor=this.polygonOffsetFactor,n.polygonOffsetUnits=this.polygonOffsetUnits,n.dithering=this.dithering,n.alphaTest=this.alphaTest,n.alphaHash=this.alphaHash,n.alphaToCoverage=this.alphaToCoverage,n.premultipliedAlpha=this.premultipliedAlpha,n.forceSinglePass=this.forceSinglePass,n.allowOverride=this.allowOverride,n.visible=this.visible,n.toneMapped=this.toneMapped,n.name=this.name,this.color&&this.color.isColor&&(n.color=this.color.getHex()),this.roughness!==void 0&&(n.roughness=this.roughness),this.metalness!==void 0&&(n.metalness=this.metalness),this.sheen!==void 0&&(n.sheen=this.sheen),this.sheenColor&&this.sheenColor.isColor&&(n.sheenColor=this.sheenColor.getHex()),this.sheenRoughness!==void 0&&(n.sheenRoughness=this.sheenRoughness),this.emissive&&this.emissive.isColor&&(n.emissive=this.emissive.getHex()),this.emissiveIntensity!==void 0&&(n.emissiveIntensity=this.emissiveIntensity),this.specular&&this.specular.isColor&&(n.specular=this.specular.getHex()),this.specularIntensity!==void 0&&(n.specularIntensity=this.specularIntensity),this.specularColor&&this.specularColor.isColor&&(n.specularColor=this.specularColor.getHex()),this.shininess!==void 0&&(n.shininess=this.shininess),this.clearcoat!==void 0&&(n.clearcoat=this.clearcoat),this.clearcoatRoughness!==void 0&&(n.clearcoatRoughness=this.clearcoatRoughness),this.clearcoatMap&&this.clearcoatMap.isTexture&&(n.clearcoatMap=this.clearcoatMap.toJSON(t).uuid),this.clearcoatRoughnessMap&&this.clearcoatRoughnessMap.isTexture&&(n.clearcoatRoughnessMap=this.clearcoatRoughnessMap.toJSON(t).uuid),this.clearcoatNormalMap&&this.clearcoatNormalMap.isTexture&&(n.clearcoatNormalMap=this.clearcoatNormalMap.toJSON(t).uuid,n.clearcoatNormalScale=this.clearcoatNormalScale.toArray()),this.sheenColorMap&&this.sheenColorMap.isTexture&&(n.sheenColorMap=this.sheenColorMap.toJSON(t).uuid),this.sheenRoughnessMap&&this.sheenRoughnessMap.isTexture&&(n.sheenRoughnessMap=this.sheenRoughnessMap.toJSON(t).uuid),this.dispersion!==void 0&&(n.dispersion=this.dispersion),this.retroreflectivity!==void 0&&(n.retroreflectivity=this.retroreflectivity),this.iridescence!==void 0&&(n.iridescence=this.iridescence),this.iridescenceIOR!==void 0&&(n.iridescenceIOR=this.iridescenceIOR),this.iridescenceThicknessRange!==void 0&&(n.iridescenceThicknessRange=this.iridescenceThicknessRange),this.iridescenceMap&&this.iridescenceMap.isTexture&&(n.iridescenceMap=this.iridescenceMap.toJSON(t).uuid),this.iridescenceThicknessMap&&this.iridescenceThicknessMap.isTexture&&(n.iridescenceThicknessMap=this.iridescenceThicknessMap.toJSON(t).uuid),this.anisotropy!==void 0&&(n.anisotropy=this.anisotropy),this.anisotropyRotation!==void 0&&(n.anisotropyRotation=this.anisotropyRotation),this.anisotropyMap&&this.anisotropyMap.isTexture&&(n.anisotropyMap=this.anisotropyMap.toJSON(t).uuid),this.map&&this.map.isTexture&&(n.map=this.map.toJSON(t).uuid),this.matcap&&this.matcap.isTexture&&(n.matcap=this.matcap.toJSON(t).uuid),this.alphaMap&&this.alphaMap.isTexture&&(n.alphaMap=this.alphaMap.toJSON(t).uuid),this.lightMap&&this.lightMap.isTexture&&(n.lightMap=this.lightMap.toJSON(t).uuid,n.lightMapIntensity=this.lightMapIntensity),this.aoMap&&this.aoMap.isTexture&&(n.aoMap=this.aoMap.toJSON(t).uuid,n.aoMapIntensity=this.aoMapIntensity),this.bumpMap&&this.bumpMap.isTexture&&(n.bumpMap=this.bumpMap.toJSON(t).uuid,n.bumpScale=this.bumpScale),this.normalMap&&this.normalMap.isTexture&&(n.normalMap=this.normalMap.toJSON(t).uuid,n.normalMapType=this.normalMapType,n.normalScale=this.normalScale.toArray()),this.displacementMap&&this.displacementMap.isTexture&&(n.displacementMap=this.displacementMap.toJSON(t).uuid,n.displacementScale=this.displacementScale,n.displacementBias=this.displacementBias),this.roughnessMap&&this.roughnessMap.isTexture&&(n.roughnessMap=this.roughnessMap.toJSON(t).uuid),this.metalnessMap&&this.metalnessMap.isTexture&&(n.metalnessMap=this.metalnessMap.toJSON(t).uuid),this.emissiveMap&&this.emissiveMap.isTexture&&(n.emissiveMap=this.emissiveMap.toJSON(t).uuid),this.specularMap&&this.specularMap.isTexture&&(n.specularMap=this.specularMap.toJSON(t).uuid),this.specularIntensityMap&&this.specularIntensityMap.isTexture&&(n.specularIntensityMap=this.specularIntensityMap.toJSON(t).uuid),this.specularColorMap&&this.specularColorMap.isTexture&&(n.specularColorMap=this.specularColorMap.toJSON(t).uuid),this.envMap&&this.envMap.isTexture&&(n.envMap=this.envMap.toJSON(t).uuid,this.combine!==void 0&&(n.combine=this.combine)),this.envMapRotation!==void 0&&(n.envMapRotation=this.envMapRotation.toArray()),this.envMapIntensity!==void 0&&(n.envMapIntensity=this.envMapIntensity),this.reflectivity!==void 0&&(n.reflectivity=this.reflectivity),this.refractionRatio!==void 0&&(n.refractionRatio=this.refractionRatio),this.gradientMap&&this.gradientMap.isTexture&&(n.gradientMap=this.gradientMap.toJSON(t).uuid),this.transmission!==void 0&&(n.transmission=this.transmission),this.transmissionMap&&this.transmissionMap.isTexture&&(n.transmissionMap=this.transmissionMap.toJSON(t).uuid),this.thickness!==void 0&&(n.thickness=this.thickness),this.thicknessMap&&this.thicknessMap.isTexture&&(n.thicknessMap=this.thicknessMap.toJSON(t).uuid),this.attenuationDistance!==void 0&&(n.attenuationDistance=this.attenuationDistance),this.attenuationColor!==void 0&&(n.attenuationColor=this.attenuationColor.getHex()),this.size!==void 0&&(n.size=this.size),this.sizeAttenuation!==void 0&&(n.sizeAttenuation=this.sizeAttenuation),Array.isArray(this.clippingPlanes)&&this.clippingPlanes.length>0&&(n.clippingPlanes=this.clippingPlanes.map(r=>r.toJSON())),this.rotation!==void 0&&(n.rotation=this.rotation),this.depthPacking!==void 0&&(n.depthPacking=this.depthPacking),this.linewidth!==void 0&&(n.linewidth=this.linewidth),this.linecap!==void 0&&(n.linecap=this.linecap),this.linejoin!==void 0&&(n.linejoin=this.linejoin),this.dashSize!==void 0&&(n.dashSize=this.dashSize),this.gapSize!==void 0&&(n.gapSize=this.gapSize),this.scale!==void 0&&(n.scale=this.scale),this.wireframe!==void 0&&(n.wireframe=this.wireframe),this.wireframeLinewidth!==void 0&&(n.wireframeLinewidth=this.wireframeLinewidth),this.wireframeLinecap!==void 0&&(n.wireframeLinecap=this.wireframeLinecap),this.wireframeLinejoin!==void 0&&(n.wireframeLinejoin=this.wireframeLinejoin),this.flatShading!==void 0&&(n.flatShading=this.flatShading),this.fog!==void 0&&(n.fog=this.fog),Object.keys(this.userData).length>0&&(n.userData=this.userData);function s(r){let a=[];for(let l in r){let o=r[l];delete o.metadata,a.push(o)}return a}if(e){let r=s(t.textures),a=s(t.images);r.length>0&&(n.textures=r),a.length>0&&(n.images=a)}return n}fromJSON(t,e){if(t.uuid!==void 0&&(this.uuid=t.uuid),t.name!==void 0&&(this.name=t.name),t.color!==void 0&&this.color!==void 0&&this.color.setHex(t.color),t.roughness!==void 0&&(this.roughness=t.roughness),t.metalness!==void 0&&(this.metalness=t.metalness),t.sheen!==void 0&&(this.sheen=t.sheen),t.sheenColor!==void 0&&(this.sheenColor=new $t().setHex(t.sheenColor)),t.sheenRoughness!==void 0&&(this.sheenRoughness=t.sheenRoughness),t.emissive!==void 0&&this.emissive!==void 0&&this.emissive.setHex(t.emissive),t.specular!==void 0&&this.specular!==void 0&&this.specular.setHex(t.specular),t.specularIntensity!==void 0&&(this.specularIntensity=t.specularIntensity),t.specularColor!==void 0&&this.specularColor!==void 0&&this.specularColor.setHex(t.specularColor),t.shininess!==void 0&&(this.shininess=t.shininess),t.clearcoat!==void 0&&(this.clearcoat=t.clearcoat),t.clearcoatRoughness!==void 0&&(this.clearcoatRoughness=t.clearcoatRoughness),t.dispersion!==void 0&&(this.dispersion=t.dispersion),t.retroreflectivity!==void 0&&(this.retroreflectivity=t.retroreflectivity),t.iridescence!==void 0&&(this.iridescence=t.iridescence),t.iridescenceIOR!==void 0&&(this.iridescenceIOR=t.iridescenceIOR),t.iridescenceThicknessRange!==void 0&&(this.iridescenceThicknessRange=t.iridescenceThicknessRange),t.transmission!==void 0&&(this.transmission=t.transmission),t.thickness!==void 0&&(this.thickness=t.thickness),t.attenuationDistance!==void 0&&(this.attenuationDistance=t.attenuationDistance),t.attenuationColor!==void 0&&this.attenuationColor!==void 0&&this.attenuationColor.setHex(t.attenuationColor),t.anisotropy!==void 0&&(this.anisotropy=t.anisotropy),t.anisotropyRotation!==void 0&&(this.anisotropyRotation=t.anisotropyRotation),t.fog!==void 0&&(this.fog=t.fog),t.flatShading!==void 0&&(this.flatShading=t.flatShading),t.blending!==void 0&&(this.blending=t.blending),t.combine!==void 0&&(this.combine=t.combine),t.side!==void 0&&(this.side=t.side),t.shadowSide!==void 0&&(this.shadowSide=t.shadowSide),t.opacity!==void 0&&(this.opacity=t.opacity),t.transparent!==void 0&&(this.transparent=t.transparent),t.alphaTest!==void 0&&(this.alphaTest=t.alphaTest),t.alphaHash!==void 0&&(this.alphaHash=t.alphaHash),t.depthFunc!==void 0&&(this.depthFunc=t.depthFunc),t.depthTest!==void 0&&(this.depthTest=t.depthTest),t.depthWrite!==void 0&&(this.depthWrite=t.depthWrite),t.colorWrite!==void 0&&(this.colorWrite=t.colorWrite),t.clippingPlanes!==void 0&&(this.clippingPlanes=t.clippingPlanes.map(n=>new Hn().fromJSON(n))),t.clipIntersection!==void 0&&(this.clipIntersection=t.clipIntersection),t.clipShadows!==void 0&&(this.clipShadows=t.clipShadows),t.depthPacking!==void 0&&(this.depthPacking=t.depthPacking),t.blendSrc!==void 0&&(this.blendSrc=t.blendSrc),t.blendDst!==void 0&&(this.blendDst=t.blendDst),t.blendEquation!==void 0&&(this.blendEquation=t.blendEquation),t.blendSrcAlpha!==void 0&&(this.blendSrcAlpha=t.blendSrcAlpha),t.blendDstAlpha!==void 0&&(this.blendDstAlpha=t.blendDstAlpha),t.blendEquationAlpha!==void 0&&(this.blendEquationAlpha=t.blendEquationAlpha),t.blendColor!==void 0&&this.blendColor!==void 0&&this.blendColor.setHex(t.blendColor),t.blendAlpha!==void 0&&(this.blendAlpha=t.blendAlpha),t.stencilWriteMask!==void 0&&(this.stencilWriteMask=t.stencilWriteMask),t.stencilFunc!==void 0&&(this.stencilFunc=t.stencilFunc),t.stencilRef!==void 0&&(this.stencilRef=t.stencilRef),t.stencilFuncMask!==void 0&&(this.stencilFuncMask=t.stencilFuncMask),t.stencilFail!==void 0&&(this.stencilFail=t.stencilFail),t.stencilZFail!==void 0&&(this.stencilZFail=t.stencilZFail),t.stencilZPass!==void 0&&(this.stencilZPass=t.stencilZPass),t.stencilWrite!==void 0&&(this.stencilWrite=t.stencilWrite),t.wireframe!==void 0&&(this.wireframe=t.wireframe),t.wireframeLinewidth!==void 0&&(this.wireframeLinewidth=t.wireframeLinewidth),t.wireframeLinecap!==void 0&&(this.wireframeLinecap=t.wireframeLinecap),t.wireframeLinejoin!==void 0&&(this.wireframeLinejoin=t.wireframeLinejoin),t.rotation!==void 0&&(this.rotation=t.rotation),t.linewidth!==void 0&&(this.linewidth=t.linewidth),t.linecap!==void 0&&(this.linecap=t.linecap),t.linejoin!==void 0&&(this.linejoin=t.linejoin),t.dashSize!==void 0&&(this.dashSize=t.dashSize),t.gapSize!==void 0&&(this.gapSize=t.gapSize),t.scale!==void 0&&(this.scale=t.scale),t.polygonOffset!==void 0&&(this.polygonOffset=t.polygonOffset),t.polygonOffsetFactor!==void 0&&(this.polygonOffsetFactor=t.polygonOffsetFactor),t.polygonOffsetUnits!==void 0&&(this.polygonOffsetUnits=t.polygonOffsetUnits),t.dithering!==void 0&&(this.dithering=t.dithering),t.alphaToCoverage!==void 0&&(this.alphaToCoverage=t.alphaToCoverage),t.premultipliedAlpha!==void 0&&(this.premultipliedAlpha=t.premultipliedAlpha),t.forceSinglePass!==void 0&&(this.forceSinglePass=t.forceSinglePass),t.allowOverride!==void 0&&(this.allowOverride=t.allowOverride),t.visible!==void 0&&(this.visible=t.visible),t.toneMapped!==void 0&&(this.toneMapped=t.toneMapped),t.userData!==void 0&&(this.userData=t.userData),t.vertexColors!==void 0&&(typeof t.vertexColors=="number"?this.vertexColors=t.vertexColors>0:this.vertexColors=t.vertexColors),t.size!==void 0&&(this.size=t.size),t.sizeAttenuation!==void 0&&(this.sizeAttenuation=t.sizeAttenuation),t.map!==void 0&&(this.map=e[t.map]||null),t.matcap!==void 0&&(this.matcap=e[t.matcap]||null),t.alphaMap!==void 0&&(this.alphaMap=e[t.alphaMap]||null),t.bumpMap!==void 0&&(this.bumpMap=e[t.bumpMap]||null),t.bumpScale!==void 0&&(this.bumpScale=t.bumpScale),t.normalMap!==void 0&&(this.normalMap=e[t.normalMap]||null),t.normalMapType!==void 0&&(this.normalMapType=t.normalMapType),t.normalScale!==void 0){let n=t.normalScale;Array.isArray(n)===!1&&(n=[n,n]),this.normalScale=new Xt().fromArray(n)}return t.displacementMap!==void 0&&(this.displacementMap=e[t.displacementMap]||null),t.displacementScale!==void 0&&(this.displacementScale=t.displacementScale),t.displacementBias!==void 0&&(this.displacementBias=t.displacementBias),t.roughnessMap!==void 0&&(this.roughnessMap=e[t.roughnessMap]||null),t.metalnessMap!==void 0&&(this.metalnessMap=e[t.metalnessMap]||null),t.emissiveMap!==void 0&&(this.emissiveMap=e[t.emissiveMap]||null),t.emissiveIntensity!==void 0&&(this.emissiveIntensity=t.emissiveIntensity),t.specularMap!==void 0&&(this.specularMap=e[t.specularMap]||null),t.specularIntensityMap!==void 0&&(this.specularIntensityMap=e[t.specularIntensityMap]||null),t.specularColorMap!==void 0&&(this.specularColorMap=e[t.specularColorMap]||null),t.envMap!==void 0&&(this.envMap=e[t.envMap]||null),t.envMapRotation!==void 0&&this.envMapRotation.fromArray(t.envMapRotation),t.envMapIntensity!==void 0&&(this.envMapIntensity=t.envMapIntensity),t.reflectivity!==void 0&&(this.reflectivity=t.reflectivity),t.refractionRatio!==void 0&&(this.refractionRatio=t.refractionRatio),t.lightMap!==void 0&&(this.lightMap=e[t.lightMap]||null),t.lightMapIntensity!==void 0&&(this.lightMapIntensity=t.lightMapIntensity),t.aoMap!==void 0&&(this.aoMap=e[t.aoMap]||null),t.aoMapIntensity!==void 0&&(this.aoMapIntensity=t.aoMapIntensity),t.gradientMap!==void 0&&(this.gradientMap=e[t.gradientMap]||null),t.clearcoatMap!==void 0&&(this.clearcoatMap=e[t.clearcoatMap]||null),t.clearcoatRoughnessMap!==void 0&&(this.clearcoatRoughnessMap=e[t.clearcoatRoughnessMap]||null),t.clearcoatNormalMap!==void 0&&(this.clearcoatNormalMap=e[t.clearcoatNormalMap]||null),t.clearcoatNormalScale!==void 0&&(this.clearcoatNormalScale=new Xt().fromArray(t.clearcoatNormalScale)),t.iridescenceMap!==void 0&&(this.iridescenceMap=e[t.iridescenceMap]||null),t.iridescenceThicknessMap!==void 0&&(this.iridescenceThicknessMap=e[t.iridescenceThicknessMap]||null),t.transmissionMap!==void 0&&(this.transmissionMap=e[t.transmissionMap]||null),t.thicknessMap!==void 0&&(this.thicknessMap=e[t.thicknessMap]||null),t.anisotropyMap!==void 0&&(this.anisotropyMap=e[t.anisotropyMap]||null),t.sheenColorMap!==void 0&&(this.sheenColorMap=e[t.sheenColorMap]||null),t.sheenRoughnessMap!==void 0&&(this.sheenRoughnessMap=e[t.sheenRoughnessMap]||null),this}clone(){return new this.constructor().copy(this)}copy(t){this.name=t.name,this.blending=t.blending,this.side=t.side,this.vertexColors=t.vertexColors,this.opacity=t.opacity,this.transparent=t.transparent,this.blendSrc=t.blendSrc,this.blendDst=t.blendDst,this.blendEquation=t.blendEquation,this.blendSrcAlpha=t.blendSrcAlpha,this.blendDstAlpha=t.blendDstAlpha,this.blendEquationAlpha=t.blendEquationAlpha,this.blendColor.copy(t.blendColor),this.blendAlpha=t.blendAlpha,this.depthFunc=t.depthFunc,this.depthTest=t.depthTest,this.depthWrite=t.depthWrite,this.stencilWriteMask=t.stencilWriteMask,this.stencilFunc=t.stencilFunc,this.stencilRef=t.stencilRef,this.stencilFuncMask=t.stencilFuncMask,this.stencilFail=t.stencilFail,this.stencilZFail=t.stencilZFail,this.stencilZPass=t.stencilZPass,this.stencilWrite=t.stencilWrite;let e=t.clippingPlanes,n=null;if(e!==null){let s=e.length;n=new Array(s);for(let r=0;r!==s;++r)n[r]=e[r].clone()}return this.clippingPlanes=n,this.clipIntersection=t.clipIntersection,this.clipShadows=t.clipShadows,this.shadowSide=t.shadowSide,this.colorWrite=t.colorWrite,this.precision=t.precision,this.polygonOffset=t.polygonOffset,this.polygonOffsetFactor=t.polygonOffsetFactor,this.polygonOffsetUnits=t.polygonOffsetUnits,this.dithering=t.dithering,this.alphaTest=t.alphaTest,this.alphaHash=t.alphaHash,this.alphaToCoverage=t.alphaToCoverage,this.premultipliedAlpha=t.premultipliedAlpha,this.forceSinglePass=t.forceSinglePass,this.allowOverride=t.allowOverride,this.visible=t.visible,this.toneMapped=t.toneMapped,this.userData=JSON.parse(JSON.stringify(t.userData)),this}dispose(){this.dispatchEvent({type:"dispose"})}set needsUpdate(t){t===!0&&this.version++}};var Wi=new F,Ac=new F,no=new F,io=new F,ks=class{constructor(t=new F,e=new F(0,0,-1)){this.origin=t,this.direction=e}set(t,e){return this.origin.copy(t),this.direction.copy(e),this}copy(t){return this.origin.copy(t.origin),this.direction.copy(t.direction),this}at(t,e){return e.copy(this.origin).addScaledVector(this.direction,t)}lookAt(t){return this.direction.copy(t).sub(this.origin).normalize(),this}recast(t){return this.origin.copy(this.at(t,Wi)),this}closestPointToPoint(t,e){e.subVectors(t,this.origin);let n=e.dot(this.direction);return n<0?e.copy(this.origin):e.copy(this.origin).addScaledVector(this.direction,n)}distanceToPoint(t){return Math.sqrt(this.distanceSqToPoint(t))}distanceSqToPoint(t){let e=Wi.subVectors(t,this.origin).dot(this.direction);return e<0?this.origin.distanceToSquared(t):(Wi.copy(this.origin).addScaledVector(this.direction,e),Wi.distanceToSquared(t))}distanceSqToSegment(t,e,n,s){Ac.copy(t).add(e).multiplyScalar(.5),no.copy(e).sub(t).normalize(),io.copy(this.origin).sub(Ac);let r=t.distanceTo(e)*.5,a=-this.direction.dot(no),l=io.dot(this.direction),o=-io.dot(no),c=io.lengthSq(),h=Math.abs(1-a*a),f,d,p,x;if(h>0)if(f=a*o-l,d=a*l-o,x=r*h,f>=0)if(d>=-x)if(d<=x){let M=1/h;f*=M,d*=M,p=f*(f+a*d+2*l)+d*(a*f+d+2*o)+c}else d=r,f=Math.max(0,-(a*d+l)),p=-f*f+d*(d+2*o)+c;else d=-r,f=Math.max(0,-(a*d+l)),p=-f*f+d*(d+2*o)+c;else d<=-x?(f=Math.max(0,-(-a*r+l)),d=f>0?-r:Math.min(Math.max(-r,-o),r),p=-f*f+d*(d+2*o)+c):d<=x?(f=0,d=Math.min(Math.max(-r,-o),r),p=d*(d+2*o)+c):(f=Math.max(0,-(a*r+l)),d=f>0?r:Math.min(Math.max(-r,-o),r),p=-f*f+d*(d+2*o)+c);else d=a>0?-r:r,f=Math.max(0,-(a*d+l)),p=-f*f+d*(d+2*o)+c;return n&&n.copy(this.origin).addScaledVector(this.direction,f),s&&s.copy(Ac).addScaledVector(no,d),p}intersectSphere(t,e){if(t.radius<0)return null;Wi.subVectors(t.center,this.origin);let n=Wi.dot(this.direction),s=Wi.dot(Wi)-n*n,r=t.radius*t.radius;if(s>r)return null;let a=Math.sqrt(r-s),l=n-a,o=n+a;return o<0?null:l<0?this.at(o,e):this.at(l,e)}intersectsSphere(t){return t.radius<0?!1:this.distanceSqToPoint(t.center)<=t.radius*t.radius}distanceToPlane(t){let e=t.normal.dot(this.direction);if(e===0)return t.distanceToPoint(this.origin)===0?0:null;let n=-(this.origin.dot(t.normal)+t.constant)/e;return n>=0?n:null}intersectPlane(t,e){let n=this.distanceToPlane(t);return n===null?null:this.at(n,e)}intersectsPlane(t){let e=t.distanceToPoint(this.origin);return e===0||t.normal.dot(this.direction)*e<0}intersectBox(t,e){let n,s,r,a,l,o,c=1/this.direction.x,h=1/this.direction.y,f=1/this.direction.z,d=this.origin;return c>=0?(n=(t.min.x-d.x)*c,s=(t.max.x-d.x)*c):(n=(t.max.x-d.x)*c,s=(t.min.x-d.x)*c),h>=0?(r=(t.min.y-d.y)*h,a=(t.max.y-d.y)*h):(r=(t.max.y-d.y)*h,a=(t.min.y-d.y)*h),n>a||r>s||((r>n||isNaN(n))&&(n=r),(a<s||isNaN(s))&&(s=a),f>=0?(l=(t.min.z-d.z)*f,o=(t.max.z-d.z)*f):(l=(t.max.z-d.z)*f,o=(t.min.z-d.z)*f),n>o||l>s)||((l>n||n!==n)&&(n=l),(o<s||s!==s)&&(s=o),s<0)?null:this.at(n>=0?n:s,e)}intersectsBox(t){return this.intersectBox(t,Wi)!==null}intersectTriangle(t,e,n,s,r){let a=this.origin,l=this.direction,o=l.x,c=l.y,h=l.z,f=t.x-a.x,d=t.y-a.y,p=t.z-a.z,x=e.x-a.x,M=e.y-a.y,m=e.z-a.z,u=n.x-a.x,b=n.y-a.y,A=n.z-a.z,v=Math.abs(o),S=Math.abs(c),E=Math.abs(h),R,g,w,T,C,D,V,U,z,q,N,G;if(v>=S&&v>=E?(w=o,D=f,z=x,G=u,o>=0?(R=c,g=h,T=d,C=p,V=M,U=m,q=b,N=A):(R=h,g=c,T=p,C=d,V=m,U=M,q=A,N=b)):S>=E?(w=c,D=d,z=M,G=b,c>=0?(R=h,g=o,T=p,C=f,V=m,U=x,q=A,N=u):(R=o,g=h,T=f,C=p,V=x,U=m,q=u,N=A)):(w=h,D=p,z=m,G=A,h>=0?(R=o,g=c,T=f,C=d,V=x,U=M,q=u,N=b):(R=c,g=o,T=d,C=f,V=M,U=x,q=b,N=u)),w===0)return null;let X=R/w,K=g/w,nt=1/w,tt=T-X*D,lt=C-K*D,zt=V-X*z,Lt=U-K*z,gt=q-X*G,J=N-K*G,et=gt*Lt-J*zt,pt=tt*J-lt*gt,At=zt*lt-Lt*tt;if(s){if(et<0||pt<0||At<0)return null}else if((et<0||pt<0||At<0)&&(et>0||pt>0||At>0))return null;let Mt=et+pt+At;if(Mt===0)return null;let qt=nt*(et*D+pt*z+At*G);return(Mt>0?qt<0:qt>0)?null:this.at(qt/Mt,r)}applyMatrix4(t){return this.origin.applyMatrix4(t),this.direction.transformDirection(t),this}equals(t){return t.origin.equals(this.origin)&&t.direction.equals(this.direction)}clone(){return new this.constructor().copy(this)}},be=class extends fs{constructor(t){super(),this.isMeshBasicMaterial=!0,this.type="MeshBasicMaterial",this.color=new $t(16777215),this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.specularMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new Ln,this.combine=qc,this.reflectivity=1,this.refractionRatio=.98,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.fog=!0,this.setValues(t)}copy(t){return super.copy(t),this.color.copy(t.color),this.map=t.map,this.lightMap=t.lightMap,this.lightMapIntensity=t.lightMapIntensity,this.aoMap=t.aoMap,this.aoMapIntensity=t.aoMapIntensity,this.specularMap=t.specularMap,this.alphaMap=t.alphaMap,this.envMap=t.envMap,this.envMapRotation.copy(t.envMapRotation),this.combine=t.combine,this.reflectivity=t.reflectivity,this.refractionRatio=t.refractionRatio,this.wireframe=t.wireframe,this.wireframeLinewidth=t.wireframeLinewidth,this.wireframeLinecap=t.wireframeLinecap,this.wireframeLinejoin=t.wireframeLinejoin,this.fog=t.fog,this}},gu=new ge,Us=new ks,so=new ds,xu=new F,ro=new F,ao=new F,oo=new F,Rc=new F,lo=new F,_u=new F,co=new F,kt=class extends on{constructor(t=new je,e=new be){super(),this.isMesh=!0,this.type="Mesh",this.geometry=t,this.material=e,this.morphTargetDictionary=void 0,this.morphTargetInfluences=void 0,this.count=1,this.updateMorphTargets()}copy(t,e){return super.copy(t,e),t.morphTargetInfluences!==void 0&&(this.morphTargetInfluences=t.morphTargetInfluences.slice()),t.morphTargetDictionary!==void 0&&(this.morphTargetDictionary=Object.assign({},t.morphTargetDictionary)),this.material=Array.isArray(t.material)?t.material.slice():t.material,this.geometry=t.geometry,this}updateMorphTargets(){let e=this.geometry.morphAttributes,n=Object.keys(e);if(n.length>0){let s=e[n[0]];if(s!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let r=0,a=s.length;r<a;r++){let l=s[r].name||String(r);this.morphTargetInfluences.push(0),this.morphTargetDictionary[l]=r}}}}getVertexPosition(t,e){let n=this.geometry,s=n.attributes.position,r=n.morphAttributes.position,a=n.morphTargetsRelative;e.fromBufferAttribute(s,t);let l=this.morphTargetInfluences;if(r&&l){lo.set(0,0,0);for(let o=0,c=r.length;o<c;o++){let h=l[o],f=r[o];h!==0&&(Rc.fromBufferAttribute(f,t),a?lo.addScaledVector(Rc,h):lo.addScaledVector(Rc.sub(e),h))}e.add(lo)}return e}intersectsFrustum(t){return t.intersectsObject(this)}raycast(t,e){let n=this.geometry,s=this.material,r=this.matrixWorld;s!==void 0&&(n.boundingSphere===null&&n.computeBoundingSphere(),so.copy(n.boundingSphere),so.applyMatrix4(r),Us.copy(t.ray).recast(t.near),!(so.containsPoint(Us.origin)===!1&&(Us.intersectSphere(so,xu)===null||Us.origin.distanceToSquared(xu)>(t.far-t.near)**2))&&(gu.copy(r).invert(),Us.copy(t.ray).applyMatrix4(gu),!(n.boundingBox!==null&&Us.intersectsBox(n.boundingBox)===!1)&&this._computeIntersections(t,e,Us)))}_computeIntersections(t,e,n){let s,r=this.geometry,a=this.material,l=r.index,o=r.attributes.position,c=r.attributes.uv,h=r.attributes.uv1,f=r.attributes.normal,d=r.groups,p=r.drawRange;if(l!==null)if(Array.isArray(a))for(let x=0,M=d.length;x<M;x++){let m=d[x],u=a[m.materialIndex],b=Math.max(m.start,p.start),A=Math.min(l.count,Math.min(m.start+m.count,p.start+p.count));for(let v=b,S=A;v<S;v+=3){let E=l.getX(v),R=l.getX(v+1),g=l.getX(v+2);s=ho(this,u,t,n,c,h,f,E,R,g),s&&(s.faceIndex=Math.floor(v/3),s.face.materialIndex=m.materialIndex,e.push(s))}}else{let x=Math.max(0,p.start),M=Math.min(l.count,p.start+p.count);for(let m=x,u=M;m<u;m+=3){let b=l.getX(m),A=l.getX(m+1),v=l.getX(m+2);s=ho(this,a,t,n,c,h,f,b,A,v),s&&(s.faceIndex=Math.floor(m/3),e.push(s))}}else if(o!==void 0)if(Array.isArray(a))for(let x=0,M=d.length;x<M;x++){let m=d[x],u=a[m.materialIndex],b=Math.max(m.start,p.start),A=Math.min(o.count,Math.min(m.start+m.count,p.start+p.count));for(let v=b,S=A;v<S;v+=3){let E=v,R=v+1,g=v+2;s=ho(this,u,t,n,c,h,f,E,R,g),s&&(s.faceIndex=Math.floor(v/3),s.face.materialIndex=m.materialIndex,e.push(s))}}else{let x=Math.max(0,p.start),M=Math.min(o.count,p.start+p.count);for(let m=x,u=M;m<u;m+=3){let b=m,A=m+1,v=m+2;s=ho(this,a,t,n,c,h,f,b,A,v),s&&(s.faceIndex=Math.floor(m/3),e.push(s))}}}};function bp(i,t,e,n,s,r,a,l){let o;if(t.side===Tn?o=n.intersectTriangle(a,r,s,!0,l):o=n.intersectTriangle(s,r,a,t.side===vs,l),o===null)return null;co.copy(l),co.applyMatrix4(i.matrixWorld);let c=e.ray.origin.distanceTo(co);return c<e.near||c>e.far?null:{distance:c,point:co.clone(),object:i}}function ho(i,t,e,n,s,r,a,l,o,c){i.getVertexPosition(l,ro),i.getVertexPosition(o,ao),i.getVertexPosition(c,oo);let h=bp(i,t,e,n,ro,ao,oo,_u);if(h){let f=new F;us.getBarycoord(_u,ro,ao,oo,f),s&&(h.uv=us.getInterpolatedAttribute(s,l,o,c,f,new Xt)),r&&(h.uv1=us.getInterpolatedAttribute(r,l,o,c,f,new Xt)),a&&(h.normal=us.getInterpolatedAttribute(a,l,o,c,f,new F),h.normal.dot(n.direction)>0&&h.normal.multiplyScalar(-1));let d={a:l,b:o,c,normal:new F,materialIndex:0};us.getNormal(ro,ao,oo,d.normal),h.face=d,h.barycoord=f}return h}var ga=class extends wn{constructor(t=null,e=1,n=1,s,r,a,l,o,c=an,h=an,f,d){super(null,a,l,o,c,h,s,r,f,d),this.isDataTexture=!0,this.image={data:t,width:e,height:n},this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}};var Cr=class extends pn{constructor(t,e,n,s=1){super(t,e,n),this.isInstancedBufferAttribute=!0,this.meshPerAttribute=s}copy(t){return super.copy(t),this.meshPerAttribute=t.meshPerAttribute,this}toJSON(){let t=super.toJSON();return t.meshPerAttribute=this.meshPerAttribute,t.isInstancedBufferAttribute=!0,t}},gr=new ge,yu=new ge,uo=[],vu=new wi,Mp=new ge,ra=new kt,aa=new ds,hi=class extends kt{constructor(t,e,n){super(t,e),this.isInstancedMesh=!0,this.instanceMatrix=new Cr(new Float32Array(n*16),16),this.instanceColor=null,this.morphTexture=null,this.count=n,this.boundingBox=null,this.boundingSphere=null;for(let s=0;s<n;s++)this.setMatrixAt(s,Mp)}computeBoundingBox(){let t=this.geometry,e=this.count;this.boundingBox===null&&(this.boundingBox=new wi),t.boundingBox===null&&t.computeBoundingBox(),this.boundingBox.makeEmpty();for(let n=0;n<e;n++)this.getMatrixAt(n,gr),vu.copy(t.boundingBox).applyMatrix4(gr),this.boundingBox.union(vu)}computeBoundingSphere(){let t=this.geometry,e=this.count;this.boundingSphere===null&&(this.boundingSphere=new ds),t.boundingSphere===null&&t.computeBoundingSphere(),this.boundingSphere.makeEmpty();for(let n=0;n<e;n++)this.getMatrixAt(n,gr),aa.copy(t.boundingSphere).applyMatrix4(gr),this.boundingSphere.union(aa)}copy(t,e){return super.copy(t,e),this.instanceMatrix.copy(t.instanceMatrix),t.morphTexture!==null&&(this.morphTexture=t.morphTexture.clone()),t.instanceColor!==null&&(this.instanceColor=t.instanceColor.clone()),this.count=t.count,t.boundingBox!==null&&(this.boundingBox=t.boundingBox.clone()),t.boundingSphere!==null&&(this.boundingSphere=t.boundingSphere.clone()),this}getColorAt(t,e){return this.instanceColor===null?e.setRGB(1,1,1):e.fromArray(this.instanceColor.array,t*3)}getMatrixAt(t,e){return e.fromArray(this.instanceMatrix.array,t*16)}getMorphAt(t,e){let n=e.morphTargetInfluences,s=this.morphTexture.source.data.data,r=n.length+1,a=t*r+1;for(let l=0;l<n.length;l++)n[l]=s[a+l]}raycast(t,e){let n=this.matrixWorld,s=this.count;if(ra.geometry=this.geometry,ra.material=this.material,ra.material!==void 0&&(this.boundingSphere===null&&this.computeBoundingSphere(),aa.copy(this.boundingSphere),aa.applyMatrix4(n),t.ray.intersectsSphere(aa)!==!1))for(let r=0;r<s;r++){this.getMatrixAt(r,gr),yu.multiplyMatrices(n,gr),ra.matrixWorld=yu,ra.raycast(t,uo);for(let a=0,l=uo.length;a<l;a++){let o=uo[a];o.instanceId=r,o.object=this,e.push(o)}uo.length=0}}setColorAt(t,e){return this.instanceColor===null&&(this.instanceColor=new Cr(new Float32Array(this.instanceMatrix.count*3).fill(1),3)),e.toArray(this.instanceColor.array,t*3),this}setMatrixAt(t,e){return e.toArray(this.instanceMatrix.array,t*16),this}setMorphAt(t,e){let n=e.morphTargetInfluences,s=n.length+1;this.morphTexture===null&&(this.morphTexture=new ga(new Float32Array(s*this.count),s,this.count,tl,Zn));let r=this.morphTexture.source.data.data,a=0;for(let c=0;c<n.length;c++)a+=n[c];let l=this.geometry.morphTargetsRelative?1:1-a,o=s*t;return r[o]=l,r.set(n,o+1),this}updateMorphTargets(){}dispose(){super.dispose(),this.morphTexture!==null&&(this.morphTexture.dispose(),this.morphTexture=null)}},Fs=new ds,Sp=new Xt(.5,.5),fo=new F,Pr=class{constructor(t=new Hn,e=new Hn,n=new Hn,s=new Hn,r=new Hn,a=new Hn){this.planes=[t,e,n,s,r,a]}set(t,e,n,s,r,a){let l=this.planes;return l[0].copy(t),l[1].copy(e),l[2].copy(n),l[3].copy(s),l[4].copy(r),l[5].copy(a),this}copy(t){let e=this.planes;for(let n=0;n<6;n++)e[n].copy(t.planes[n]);return this}setFromProjectionMatrix(t,e=li,n=!1){let s=this.planes,r=t.elements,a=r[0],l=r[1],o=r[2],c=r[3],h=r[4],f=r[5],d=r[6],p=r[7],x=r[8],M=r[9],m=r[10],u=r[11],b=r[12],A=r[13],v=r[14],S=r[15];if(s[0].setComponents(c-a,p-h,u-x,S-b).normalize(),s[1].setComponents(c+a,p+h,u+x,S+b).normalize(),s[2].setComponents(c+l,p+f,u+M,S+A).normalize(),s[3].setComponents(c-l,p-f,u-M,S-A).normalize(),n)s[4].setComponents(o,d,m,v).normalize(),s[5].setComponents(c-o,p-d,u-m,S-v).normalize();else if(s[4].setComponents(c-o,p-d,u-m,S-v).normalize(),e===li)s[5].setComponents(c+o,p+d,u+m,S+v).normalize();else if(e===Sr)s[5].setComponents(o,d,m,v).normalize();else throw new Error("THREE.Frustum.setFromProjectionMatrix(): Invalid coordinate system: "+e);return this}intersectsObject(t){if(t.boundingSphere!==void 0)t.boundingSphere===null&&t.computeBoundingSphere(),Fs.copy(t.boundingSphere).applyMatrix4(t.matrixWorld);else{let e=t.geometry;e.boundingSphere===null&&e.computeBoundingSphere(),Fs.copy(e.boundingSphere).applyMatrix4(t.matrixWorld)}return this.intersectsSphere(Fs)}intersectsSprite(t){Fs.center.set(0,0,0);let e=Sp.distanceTo(t.center);return Fs.radius=.7071067811865476+e,Fs.applyMatrix4(t.matrixWorld),this.intersectsSphere(Fs)}intersectsSphere(t){let e=this.planes,n=t.center,s=-t.radius;for(let r=0;r<6;r++)if(e[r].distanceToPoint(n)<s)return!1;return!0}intersectsBox(t){let e=this.planes;for(let n=0;n<6;n++){let s=e[n];if(fo.x=s.normal.x>0?t.max.x:t.min.x,fo.y=s.normal.y>0?t.max.y:t.min.y,fo.z=s.normal.z>0?t.max.z:t.min.z,s.distanceToPoint(fo)<0)return!1}return!0}containsPoint(t){let e=this.planes;for(let n=0;n<6;n++)if(e[n].distanceToPoint(t)<0)return!1;return!0}clone(){return new this.constructor().copy(this)}};var xa=class extends wn{constructor(t=[],e=bs,n,s,r,a,l,o,c,h){super(t,e,n,s,r,a,l,o,c,h),this.isCubeTexture=!0,this.flipY=!1}get images(){return this.image}set images(t){this.image=t}},qi=class extends wn{constructor(t,e,n,s,r,a,l,o,c){super(t,e,n,s,r,a,l,o,c),this.isCanvasTexture=!0,this.needsUpdate=!0}};var ps=class extends wn{constructor(t,e,n=di,s,r,a,l=an,o=an,c,h=Ei,f=1){if(h!==Ei&&h!==Ss)throw new Error("THREE.DepthTexture: format must be either THREE.DepthFormat or THREE.DepthStencilFormat");let d={width:t,height:e,depth:f};super(d,s,r,a,l,o,h,n,c),this.isDepthTexture=!0,this.flipY=!1,this.generateMipmaps=!1,this.compareFunction=null}copy(t){return super.copy(t),this.source=new Tr(Object.assign({},t.image)),this.compareFunction=t.compareFunction,this}toJSON(t){let e=super.toJSON(t);return e.compareFunction=this.compareFunction,e}},Po=class extends ps{constructor(t,e=di,n=bs,s,r,a=an,l=an,o,c=Ei){let h={width:t,height:t,depth:1},f=[h,h,h,h,h,h];super(t,t,e,n,s,r,a,l,o,c),this.image=f,this.isCubeDepthTexture=!0,this.isCubeTexture=!0}get images(){return this.image}set images(t){this.image=t}},_a=class extends wn{constructor(t=null){super(),this.sourceTexture=t,this.isExternalTexture=!0}copy(t){return super.copy(t),this.sourceTexture=t.sourceTexture,this}},ce=class i extends je{constructor(t=1,e=1,n=1,s=1,r=1,a=1){super(),this.type="BoxGeometry",this.parameters={width:t,height:e,depth:n,widthSegments:s,heightSegments:r,depthSegments:a};let l=this;s=Math.floor(s),r=Math.floor(r),a=Math.floor(a);let o=[],c=[],h=[],f=[],d=0,p=0;x("z","y","x",-1,-1,n,e,t,a,r,0),x("z","y","x",1,-1,n,e,-t,a,r,1),x("x","z","y",1,1,t,n,e,s,a,2),x("x","z","y",1,-1,t,n,-e,s,a,3),x("x","y","z",1,-1,t,e,n,s,r,4),x("x","y","z",-1,-1,t,e,-n,s,r,5),this.setIndex(o),this.setAttribute("position",new Ee(c,3)),this.setAttribute("normal",new Ee(h,3)),this.setAttribute("uv",new Ee(f,2));function x(M,m,u,b,A,v,S,E,R,g,w){let T=v/R,C=S/g,D=v/2,V=S/2,U=E/2,z=R+1,q=g+1,N=0,G=0,X=new F;for(let K=0;K<q;K++){let nt=K*C-V;for(let tt=0;tt<z;tt++){let lt=tt*T-D;X[M]=lt*b,X[m]=nt*A,X[u]=U,c.push(X.x,X.y,X.z),X[M]=0,X[m]=0,X[u]=E>0?1:-1,h.push(X.x,X.y,X.z),f.push(tt/R),f.push(1-K/g),N+=1}}for(let K=0;K<g;K++)for(let nt=0;nt<R;nt++){let tt=d+nt+z*K,lt=d+nt+z*(K+1),zt=d+(nt+1)+z*(K+1),Lt=d+(nt+1)+z*K;o.push(tt,lt,Lt),o.push(lt,zt,Lt),G+=6}l.addGroup(p,G,w),p+=G,d+=N}}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.width,t.height,t.depth,t.widthSegments,t.heightSegments,t.depthSegments)}},ya=class i extends je{constructor(t=1,e=1,n=4,s=8,r=1){super(),this.type="CapsuleGeometry",this.parameters={radius:t,height:e,capSegments:n,radialSegments:s,heightSegments:r},e=Math.max(0,e),n=Math.max(1,Math.floor(n)),s=Math.max(3,Math.floor(s)),r=Math.max(1,Math.floor(r));let a=[],l=[],o=[],c=[],h=e/2,f=Math.PI/2*t,d=e,p=2*f+d,x=n*2+r,M=s+1,m=new F,u=new F;for(let b=0;b<=x;b++){let A=0,v=0,S=0,E=0;if(b<=n){let w=b/n,T=w*Math.PI/2;v=-h-t*Math.cos(T),S=t*Math.sin(T),E=-t*Math.cos(T),A=w*f}else if(b<=n+r){let w=(b-n)/r;v=-h+w*e,S=t,E=0,A=f+w*d}else{let w=(b-n-r)/n,T=w*Math.PI/2;v=h+t*Math.sin(T),S=t*Math.cos(T),E=t*Math.sin(T),A=f+d+w*f}let R=Math.max(0,Math.min(1,A/p)),g=0;b===0?g=.5/s:b===x&&(g=-.5/s);for(let w=0;w<=s;w++){let T=w/s,C=T*Math.PI*2,D=Math.sin(C),V=Math.cos(C);u.x=-S*V,u.y=v,u.z=S*D,l.push(u.x,u.y,u.z),m.set(-S*V,E,S*D),m.normalize(),o.push(m.x,m.y,m.z),c.push(T+g,R)}if(b>0){let w=(b-1)*M;for(let T=0;T<s;T++){let C=w+T,D=w+T+1,V=b*M+T,U=b*M+T+1;a.push(C,D,V),a.push(D,U,V)}}}this.setIndex(a),this.setAttribute("position",new Ee(l,3)),this.setAttribute("normal",new Ee(o,3)),this.setAttribute("uv",new Ee(c,2))}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.radius,t.height,t.capSegments,t.radialSegments,t.heightSegments)}};var Ir=class i extends je{constructor(t=1,e=1,n=1,s=32,r=1,a=!1,l=0,o=Math.PI*2){super(),this.type="CylinderGeometry",this.parameters={radiusTop:t,radiusBottom:e,height:n,radialSegments:s,heightSegments:r,openEnded:a,thetaStart:l,thetaLength:o};let c=this;s=Math.floor(s),r=Math.floor(r);let h=[],f=[],d=[],p=[],x=0,M=[],m=n/2,u=0;b(),a===!1&&(t>0&&A(!0),e>0&&A(!1)),this.setIndex(h),this.setAttribute("position",new Ee(f,3)),this.setAttribute("normal",new Ee(d,3)),this.setAttribute("uv",new Ee(p,2));function b(){let v=new F,S=new F,E=0,R=(e-t)/n;for(let g=0;g<=r;g++){let w=[],T=g/r,C=T*(e-t)+t;for(let D=0;D<=s;D++){let V=D/s,U=V*o+l,z=Math.sin(U),q=Math.cos(U);S.x=C*z,S.y=-T*n+m,S.z=C*q,f.push(S.x,S.y,S.z),v.set(z,R,q).normalize(),d.push(v.x,v.y,v.z),p.push(V,1-T),w.push(x++)}M.push(w)}for(let g=0;g<s;g++)for(let w=0;w<r;w++){let T=M[w][g],C=M[w+1][g],D=M[w+1][g+1],V=M[w][g+1];(t>0||w!==0)&&(h.push(T,C,V),E+=3),(e>0||w!==r-1)&&(h.push(C,D,V),E+=3)}c.addGroup(u,E,0),u+=E}function A(v){let S=x,E=new Xt,R=new F,g=0,w=v===!0?t:e,T=v===!0?1:-1;for(let D=1;D<=s;D++)f.push(0,m*T,0),d.push(0,T,0),p.push(.5,.5),x++;let C=x;for(let D=0;D<=s;D++){let U=D/s*o+l,z=Math.cos(U),q=Math.sin(U);R.x=w*q,R.y=m*T,R.z=w*z,f.push(R.x,R.y,R.z),d.push(0,T,0),E.x=z*.5+.5,E.y=q*.5*T+.5,p.push(E.x,E.y),x++}for(let D=0;D<s;D++){let V=S+D,U=C+D;v===!0?h.push(U,U+1,V):h.push(U+1,U,V),g+=3}c.addGroup(u,g,v===!0?1:2),u+=g}}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.radiusTop,t.radiusBottom,t.height,t.radialSegments,t.heightSegments,t.openEnded,t.thetaStart,t.thetaLength)}},va=class i extends Ir{constructor(t=1,e=1,n=32,s=1,r=!1,a=0,l=Math.PI*2){super(0,t,e,n,s,r,a,l),this.type="ConeGeometry",this.parameters={radius:t,height:e,radialSegments:n,heightSegments:s,openEnded:r,thetaStart:a,thetaLength:l}}static fromJSON(t){return new i(t.radius,t.height,t.radialSegments,t.heightSegments,t.openEnded,t.thetaStart,t.thetaLength)}},Io=class i extends je{constructor(t=[],e=[],n=1,s=0){super(),this.type="PolyhedronGeometry",this.parameters={vertices:t,indices:e,radius:n,detail:s};let r=[],a=[];l(s),c(n),h(),this.setAttribute("position",new Ee(r,3)),this.setAttribute("normal",new Ee(r.slice(),3)),this.setAttribute("uv",new Ee(a,2)),s===0?this.computeVertexNormals():this.normalizeNormals();function l(b){let A=new F,v=new F,S=new F;for(let E=0;E<e.length;E+=3)p(e[E+0],A),p(e[E+1],v),p(e[E+2],S),o(A,v,S,b)}function o(b,A,v,S){let E=S+1,R=[];for(let g=0;g<=E;g++){R[g]=[];let w=b.clone().lerp(v,g/E),T=A.clone().lerp(v,g/E),C=E-g;for(let D=0;D<=C;D++)D===0&&g===E?R[g][D]=w:R[g][D]=w.clone().lerp(T,D/C)}for(let g=0;g<E;g++)for(let w=0;w<2*(E-g)-1;w++){let T=Math.floor(w/2);w%2===0?(d(R[g][T+1]),d(R[g+1][T]),d(R[g][T])):(d(R[g][T+1]),d(R[g+1][T+1]),d(R[g+1][T]))}}function c(b){let A=new F;for(let v=0;v<r.length;v+=3)A.x=r[v+0],A.y=r[v+1],A.z=r[v+2],A.normalize().multiplyScalar(b),r[v+0]=A.x,r[v+1]=A.y,r[v+2]=A.z}function h(){let b=new F;for(let A=0;A<r.length;A+=3){b.x=r[A+0],b.y=r[A+1],b.z=r[A+2];let v=m(b)/2/Math.PI+.5,S=u(b)/Math.PI+.5;a.push(v,1-S)}x(),f()}function f(){for(let b=0;b<a.length;b+=6){let A=a[b+0],v=a[b+2],S=a[b+4],E=Math.max(A,v,S),R=Math.min(A,v,S);E>.9&&R<.1&&(A<.2&&(a[b+0]+=1),v<.2&&(a[b+2]+=1),S<.2&&(a[b+4]+=1))}}function d(b){r.push(b.x,b.y,b.z)}function p(b,A){let v=b*3;A.x=t[v+0],A.y=t[v+1],A.z=t[v+2]}function x(){let b=new F,A=new F,v=new F,S=new F,E=new Xt,R=new Xt,g=new Xt;for(let w=0,T=0;w<r.length;w+=9,T+=6){b.set(r[w+0],r[w+1],r[w+2]),A.set(r[w+3],r[w+4],r[w+5]),v.set(r[w+6],r[w+7],r[w+8]),E.set(a[T+0],a[T+1]),R.set(a[T+2],a[T+3]),g.set(a[T+4],a[T+5]),S.copy(b).add(A).add(v).divideScalar(3);let C=m(S);M(E,T+0,b,C),M(R,T+2,A,C),M(g,T+4,v,C)}}function M(b,A,v,S){S<0&&b.x===1&&(a[A]=b.x-1),v.x===0&&v.z===0&&(a[A]=S/2/Math.PI+.5)}function m(b){return Math.atan2(b.z,-b.x)}function u(b){return Math.atan2(-b.y,Math.sqrt(b.x*b.x+b.z*b.z))}}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.vertices,t.indices,t.radius,t.detail)}},ba=class i extends Io{constructor(t=1,e=0){let n=(1+Math.sqrt(5))/2,s=1/n,r=[-1,-1,-1,-1,-1,1,-1,1,-1,-1,1,1,1,-1,-1,1,-1,1,1,1,-1,1,1,1,0,-s,-n,0,-s,n,0,s,-n,0,s,n,-s,-n,0,-s,n,0,s,-n,0,s,n,0,-n,0,-s,n,0,-s,-n,0,s,n,0,s],a=[3,11,7,3,7,15,3,15,13,7,19,17,7,17,6,7,6,15,17,4,8,17,8,10,17,10,6,8,0,16,8,16,2,8,2,10,0,12,1,0,1,18,0,18,16,6,10,2,6,2,13,6,13,15,2,16,18,2,18,3,2,3,13,18,1,9,18,9,11,18,11,3,4,14,12,4,12,0,4,0,8,11,9,5,11,5,19,11,19,7,19,5,14,19,14,4,19,4,17,1,12,14,1,14,5,1,5,9];super(r,a,t,e),this.type="DodecahedronGeometry",this.parameters={radius:t,detail:e}}static fromJSON(t){return new i(t.radius,t.detail)}};var Hs=class i extends je{constructor(t=1,e=1,n=1,s=1){super(),this.type="PlaneGeometry",this.parameters={width:t,height:e,widthSegments:n,heightSegments:s};let r=t/2,a=e/2,l=Math.floor(n),o=Math.floor(s),c=l+1,h=o+1,f=t/l,d=e/o,p=[],x=[],M=[],m=[];for(let u=0;u<h;u++){let b=u*d-a;for(let A=0;A<c;A++){let v=A*f-r;x.push(v,-b,0),M.push(0,0,1),m.push(A/l),m.push(1-u/o)}}for(let u=0;u<o;u++)for(let b=0;b<l;b++){let A=b+c*u,v=b+c*(u+1),S=b+1+c*(u+1),E=b+1+c*u;p.push(A,v,E),p.push(v,S,E)}this.setIndex(p),this.setAttribute("position",new Ee(x,3)),this.setAttribute("normal",new Ee(M,3)),this.setAttribute("uv",new Ee(m,2))}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.width,t.height,t.widthSegments,t.heightSegments)}};var Vs=class i extends je{constructor(t=1,e=32,n=16,s=0,r=Math.PI*2,a=0,l=Math.PI){super(),this.type="SphereGeometry",this.parameters={radius:t,widthSegments:e,heightSegments:n,phiStart:s,phiLength:r,thetaStart:a,thetaLength:l},e=Math.max(3,Math.floor(e)),n=Math.max(2,Math.floor(n));let o=Math.min(a+l,Math.PI),c=0,h=[],f=new F,d=new F,p=[],x=[],M=[],m=[];for(let u=0;u<=n;u++){let b=[],A=u/n,v=a+A*l,S=t*Math.cos(v),E=Math.sqrt(t*t-S*S),R=0;u===0&&a===0?R=.5/e:u===n&&o===Math.PI&&(R=-.5/e);for(let g=0;g<=e;g++){let w=g/e,T=s+w*r;f.x=-E*Math.cos(T),f.y=S,f.z=E*Math.sin(T),x.push(f.x,f.y,f.z),d.copy(f).normalize(),M.push(d.x,d.y,d.z),m.push(w+R,1-A),b.push(c++)}h.push(b)}for(let u=0;u<n;u++)for(let b=0;b<e;b++){let A=h[u][b+1],v=h[u][b],S=h[u+1][b],E=h[u+1][b+1];(u!==0||a>0)&&p.push(A,v,E),(u!==n-1||o<Math.PI)&&p.push(v,S,E)}this.setIndex(p),this.setAttribute("position",new Ee(x,3)),this.setAttribute("normal",new Ee(M,3)),this.setAttribute("uv",new Ee(m,2))}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.radius,t.widthSegments,t.heightSegments,t.phiStart,t.phiLength,t.thetaStart,t.thetaLength)}};var Ma=class i extends je{constructor(t=1,e=.4,n=12,s=48,r=Math.PI*2,a=0,l=Math.PI*2){super(),this.type="TorusGeometry",this.parameters={radius:t,tube:e,radialSegments:n,tubularSegments:s,arc:r,thetaStart:a,thetaLength:l},n=Math.floor(n),s=Math.floor(s);let o=[],c=[],h=[],f=[],d=new F,p=new F,x=new F;for(let M=0;M<=n;M++){let m=a+M/n*l;for(let u=0;u<=s;u++){let b=u/s*r;p.x=(t+e*Math.cos(m))*Math.cos(b),p.y=(t+e*Math.cos(m))*Math.sin(b),p.z=e*Math.sin(m),c.push(p.x,p.y,p.z),d.x=t*Math.cos(b),d.y=t*Math.sin(b),x.subVectors(p,d).normalize(),h.push(x.x,x.y,x.z),f.push(u/s),f.push(M/n)}}for(let M=1;M<=n;M++)for(let m=1;m<=s;m++){let u=(s+1)*M+m-1,b=(s+1)*(M-1)+m-1,A=(s+1)*(M-1)+m,v=(s+1)*M+m;o.push(u,b,v),o.push(b,A,v)}this.setIndex(o),this.setAttribute("position",new Ee(c,3)),this.setAttribute("normal",new Ee(h,3)),this.setAttribute("uv",new Ee(f,2))}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.radius,t.tube,t.radialSegments,t.tubularSegments,t.arc,t.thetaStart,t.thetaLength)}};function Zs(i){let t={};for(let e in i){t[e]={};for(let n in i[e]){let s=i[e][n];if(bu(s))s.isRenderTargetTexture?(Zt("UniformsUtils: Textures of render targets cannot be cloned via cloneUniforms() or mergeUniforms()."),t[e][n]=null):t[e][n]=s.clone();else if(Array.isArray(s))if(bu(s[0])){let r=[];for(let a=0,l=s.length;a<l;a++)r[a]=s[a].clone();t[e][n]=r}else t[e][n]=s.slice();else t[e][n]=s}}return t}function yn(i){let t={};for(let e=0;e<i.length;e++){let n=Zs(i[e]);for(let s in n)t[s]=n[s]}return t}function bu(i){return i&&(i.isColor||i.isMatrix3||i.isMatrix4||i.isVector2||i.isVector3||i.isVector4||i.isTexture||i.isQuaternion)}function Ep(i){let t=[];for(let e=0;e<i.length;e++)t.push(i[e].clone());return t}function ch(i){let t=i.getRenderTarget();return t===null?i.outputColorSpace:t.isXRRenderTarget===!0?t.texture.colorSpace:me.workingColorSpace}var pd={clone:Zs,merge:yn},wp=`void main() {
	gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}`,Tp=`void main() {
	gl_FragColor = vec4( 1.0, 0.0, 0.0, 1.0 );
}`,Vn=class extends fs{constructor(t){super(),this.isShaderMaterial=!0,this.type="ShaderMaterial",this.defines={},this.uniforms={},this.uniformsGroups=[],this.vertexShader=wp,this.fragmentShader=Tp,this.linewidth=1,this.wireframe=!1,this.wireframeLinewidth=1,this.fog=!1,this.lights=!1,this.clipping=!1,this.forceSinglePass=!0,this.extensions={clipCullDistance:!1,multiDraw:!1},this.defaultAttributeValues={color:[1,1,1],uv:[0,0],uv1:[0,0]},this.index0AttributeName=void 0,this.uniformsNeedUpdate=!1,this.glslVersion=null,t!==void 0&&this.setValues(t)}copy(t){return super.copy(t),this.fragmentShader=t.fragmentShader,this.vertexShader=t.vertexShader,this.uniforms=Zs(t.uniforms),this.uniformsGroups=Ep(t.uniformsGroups),this.defines=Object.assign({},t.defines),this.wireframe=t.wireframe,this.wireframeLinewidth=t.wireframeLinewidth,this.fog=t.fog,this.lights=t.lights,this.clipping=t.clipping,this.extensions=Object.assign({},t.extensions),this.glslVersion=t.glslVersion,this.defaultAttributeValues=Object.assign({},t.defaultAttributeValues),this.index0AttributeName=t.index0AttributeName,this.uniformsNeedUpdate=t.uniformsNeedUpdate,this}toJSON(t){let e=super.toJSON(t);e.glslVersion=this.glslVersion,e.uniforms={};for(let s in this.uniforms){let a=this.uniforms[s].value;a&&a.isTexture?e.uniforms[s]={type:"t",value:a.toJSON(t).uuid}:a&&a.isColor?e.uniforms[s]={type:"c",value:a.getHex()}:a&&a.isVector2?e.uniforms[s]={type:"v2",value:a.toArray()}:a&&a.isVector3?e.uniforms[s]={type:"v3",value:a.toArray()}:a&&a.isVector4?e.uniforms[s]={type:"v4",value:a.toArray()}:a&&a.isMatrix3?e.uniforms[s]={type:"m3",value:a.toArray()}:a&&a.isMatrix4?e.uniforms[s]={type:"m4",value:a.toArray()}:e.uniforms[s]={value:a}}Object.keys(this.defines).length>0&&(e.defines=this.defines),e.vertexShader=this.vertexShader,e.fragmentShader=this.fragmentShader,e.lights=this.lights,e.clipping=this.clipping;let n={};for(let s in this.extensions)this.extensions[s]===!0&&(n[s]=!0);return Object.keys(n).length>0&&(e.extensions=n),e}fromJSON(t,e){if(super.fromJSON(t,e),t.uniforms!==void 0)for(let n in t.uniforms){let s=t.uniforms[n];switch(this.uniforms[n]={},s.type){case"t":this.uniforms[n].value=e[s.value]||null;break;case"c":this.uniforms[n].value=new $t().setHex(s.value);break;case"v2":this.uniforms[n].value=new Xt().fromArray(s.value);break;case"v3":this.uniforms[n].value=new F().fromArray(s.value);break;case"v4":this.uniforms[n].value=new ke().fromArray(s.value);break;case"m3":this.uniforms[n].value=new Qt().fromArray(s.value);break;case"m4":this.uniforms[n].value=new ge().fromArray(s.value);break;default:this.uniforms[n].value=s.value}}if(t.defines!==void 0&&(this.defines=t.defines),t.vertexShader!==void 0&&(this.vertexShader=t.vertexShader),t.fragmentShader!==void 0&&(this.fragmentShader=t.fragmentShader),t.glslVersion!==void 0&&(this.glslVersion=t.glslVersion),t.extensions!==void 0)for(let n in t.extensions)this.extensions[n]=t.extensions[n];return t.lights!==void 0&&(this.lights=t.lights),t.clipping!==void 0&&(this.clipping=t.clipping),this}},Lo=class extends Vn{constructor(t){super(t),this.isRawShaderMaterial=!0,this.type="RawShaderMaterial"}},Me=class extends fs{constructor(t){super(),this.isMeshStandardMaterial=!0,this.type="MeshStandardMaterial",this.defines={STANDARD:""},this.color=new $t(16777215),this.roughness=1,this.metalness=0,this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.emissive=new $t(0),this.emissiveIntensity=1,this.emissiveMap=null,this.bumpMap=null,this.bumpScale=1,this.normalMap=null,this.normalMapType=Dl,this.normalScale=new Xt(1,1),this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.roughnessMap=null,this.metalnessMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new Ln,this.envMapIntensity=1,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.flatShading=!1,this.fog=!0,this.setValues(t)}copy(t){return super.copy(t),this.defines={STANDARD:""},this.color.copy(t.color),this.roughness=t.roughness,this.metalness=t.metalness,this.map=t.map,this.lightMap=t.lightMap,this.lightMapIntensity=t.lightMapIntensity,this.aoMap=t.aoMap,this.aoMapIntensity=t.aoMapIntensity,this.emissive.copy(t.emissive),this.emissiveMap=t.emissiveMap,this.emissiveIntensity=t.emissiveIntensity,this.bumpMap=t.bumpMap,this.bumpScale=t.bumpScale,this.normalMap=t.normalMap,this.normalMapType=t.normalMapType,this.normalScale.copy(t.normalScale),this.displacementMap=t.displacementMap,this.displacementScale=t.displacementScale,this.displacementBias=t.displacementBias,this.roughnessMap=t.roughnessMap,this.metalnessMap=t.metalnessMap,this.alphaMap=t.alphaMap,this.envMap=t.envMap,this.envMapRotation.copy(t.envMapRotation),this.envMapIntensity=t.envMapIntensity,this.wireframe=t.wireframe,this.wireframeLinewidth=t.wireframeLinewidth,this.wireframeLinecap=t.wireframeLinecap,this.wireframeLinejoin=t.wireframeLinejoin,this.flatShading=t.flatShading,this.fog=t.fog,this}};var zo=class extends fs{constructor(t){super(),this.isMeshDepthMaterial=!0,this.type="MeshDepthMaterial",this.depthPacking=Qu,this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.wireframe=!1,this.wireframeLinewidth=1,this.setValues(t)}copy(t){return super.copy(t),this.depthPacking=t.depthPacking,this.map=t.map,this.alphaMap=t.alphaMap,this.displacementMap=t.displacementMap,this.displacementScale=t.displacementScale,this.displacementBias=t.displacementBias,this.wireframe=t.wireframe,this.wireframeLinewidth=t.wireframeLinewidth,this}},Do=class extends fs{constructor(t){super(),this.isMeshDistanceMaterial=!0,this.type="MeshDistanceMaterial",this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.setValues(t)}copy(t){return super.copy(t),this.map=t.map,this.alphaMap=t.alphaMap,this.displacementMap=t.displacementMap,this.displacementScale=t.displacementScale,this.displacementBias=t.displacementBias,this}};function xr(i,t){return!i||i.constructor===t?i:typeof t.BYTES_PER_ELEMENT=="number"?new t(i):Array.prototype.slice.call(i)}function Cc(i){return i!==void 0&&i.inTangents!==void 0&&i.outTangents!==void 0}var ms=class{constructor(t,e,n,s){this.parameterPositions=t,this._cachedIndex=0,this.resultBuffer=s!==void 0?s:new e.constructor(n),this.sampleValues=e,this.valueSize=n,this.settings=null,this.DefaultSettings_={}}evaluate(t){let e=this.parameterPositions,n=this._cachedIndex,s=e[n],r=e[n-1];n:{t:{let a;e:{i:if(!(t<s)){for(let l=n+2;;){if(s===void 0){if(t<r)break i;return n=e.length,this._cachedIndex=n,this.copySampleValue_(n-1)}if(n===l)break;if(r=s,s=e[++n],t<s)break t}a=e.length;break e}if(!(t>=r)){let l=e[1];t<l&&(n=2,r=l);for(let o=n-2;;){if(r===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(n===o)break;if(s=r,r=e[--n-1],t>=r)break t}a=n,n=0;break e}break n}for(;n<a;){let l=n+a>>>1;t<e[l]?a=l:n=l+1}if(s=e[n],r=e[n-1],r===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(s===void 0)return n=e.length,this._cachedIndex=n,this.copySampleValue_(n-1)}this._cachedIndex=n,this.intervalChanged_(n,r,s)}return this.interpolate_(n,r,t,s)}getSettings_(){return this.settings||this.DefaultSettings_}copySampleValue_(t){let e=this.resultBuffer,n=this.sampleValues,s=this.valueSize,r=t*s;for(let a=0;a!==s;++a)e[a]=n[r+a];return e}interpolate_(){throw new Error("THREE.Interpolant: Call to abstract method.")}intervalChanged_(){}},No=class extends ms{constructor(t,e,n,s){super(t,e,n,s),this._weightPrev=-0,this._offsetPrev=-0,this._weightNext=-0,this._offsetNext=-0,this.DefaultSettings_={endingStart:Lc,endingEnd:Lc}}intervalChanged_(t,e,n){let s=this.parameterPositions,r=t-2,a=t+1,l=s[r],o=s[a];if(l===void 0)switch(this.getSettings_().endingStart){case zc:r=t,l=2*e-n;break;case Dc:r=s.length-2,l=e+s[r]-s[r+1];break;default:r=t,l=n}if(o===void 0)switch(this.getSettings_().endingEnd){case zc:a=t,o=2*n-e;break;case Dc:a=1,o=n+s[1]-s[0];break;default:a=t-1,o=e}let c=(n-e)*.5,h=this.valueSize;this._weightPrev=c/(e-l),this._weightNext=c/(o-n),this._offsetPrev=r*h,this._offsetNext=a*h}interpolate_(t,e,n,s){let r=this.resultBuffer,a=this.sampleValues,l=this.valueSize,o=t*l,c=o-l,h=this._offsetPrev,f=this._offsetNext,d=this._weightPrev,p=this._weightNext,x=(n-e)/(s-e),M=x*x,m=M*x,u=-d*m+2*d*M-d*x,b=(1+d)*m+(-1.5-2*d)*M+(-.5+d)*x+1,A=(-1-p)*m+(1.5+p)*M+.5*x,v=p*m-p*M;for(let S=0;S!==l;++S)r[S]=u*a[h+S]+b*a[c+S]+A*a[o+S]+v*a[f+S];return r}},Uo=class extends ms{constructor(t,e,n,s){super(t,e,n,s)}interpolate_(t,e,n,s){let r=this.resultBuffer,a=this.sampleValues,l=this.valueSize,o=t*l,c=o-l,h=(n-e)/(s-e),f=1-h;for(let d=0;d!==l;++d)r[d]=a[c+d]*f+a[o+d]*h;return r}},Fo=class extends ms{constructor(t,e,n,s){super(t,e,n,s)}interpolate_(t){return this.copySampleValue_(t-1)}},Oo=class extends ms{interpolate_(t,e,n,s){let r=this.resultBuffer,a=this.sampleValues,l=this.valueSize,o=t*l,c=o-l,h=this.inTangents,f=this.outTangents;if(!h||!f){let x=(n-e)/(s-e),M=1-x;for(let m=0;m!==l;++m)r[m]=a[c+m]*M+a[o+m]*x;return r}let d=l*2,p=t-1;for(let x=0;x!==l;++x){let M=a[c+x],m=a[o+x],u=p*d+x*2,b=f[u],A=f[u+1],v=t*d+x*2,S=h[v],E=h[v+1],R=Rp(n,e,b,S,s);r[x]=md(R,M,A,E,m)}return r}};function md(i,t,e,n,s){let r=1-i;return r*r*r*t+3*r*r*i*e+3*r*i*i*n+i*i*i*s}function Ap(i,t,e,n,s){let r=1-i;return 3*r*r*(e-t)+6*r*i*(n-e)+3*i*i*(s-n)}function Rp(i,t,e,n,s){let r=(i-t)/(s-t);for(let a=0;a<8;a++){let l=md(r,t,e,n,s)-i;if(Math.abs(l)<1e-10)break;let o=Ap(r,t,e,n,s);if(Math.abs(o)<1e-10)break;r=Math.max(0,Math.min(1,r-l/o))}return r}var Gn=class{constructor(t,e,n,s){if(t===void 0)throw new Error("THREE.KeyframeTrack: track name is undefined");if(e===void 0||e.length===0)throw new Error("THREE.KeyframeTrack: no keyframes in track named "+t);this.name=t,this.times=xr(e,this.TimeBufferType),this.values=xr(n,this.ValueBufferType),this.setInterpolation(s||this.DefaultInterpolation)}static toJSON(t){let e=t.constructor,n;if(e.toJSON!==this.toJSON)n=e.toJSON(t);else{n={name:t.name,times:xr(t.times,Array),values:xr(t.values,Array)};let s=t.getInterpolation();s!==t.DefaultInterpolation&&(n.interpolation=s),Cc(t.settings)&&(n.settings={inTangents:xr(t.settings.inTangents,Array),outTangents:xr(t.settings.outTangents,Array)})}return n.type=t.ValueTypeName,n}InterpolantFactoryMethodDiscrete(t){return new Fo(this.times,this.values,this.getValueSize(),t)}InterpolantFactoryMethodLinear(t){return new Uo(this.times,this.values,this.getValueSize(),t)}InterpolantFactoryMethodSmooth(t){return new No(this.times,this.values,this.getValueSize(),t)}InterpolantFactoryMethodBezier(t){let e=new Oo(this.times,this.values,this.getValueSize(),t);return this.settings&&(e.inTangents=this.settings.inTangents,e.outTangents=this.settings.outTangents),e}setInterpolation(t){let e;switch(t){case ca:e=this.InterpolantFactoryMethodDiscrete;break;case To:e=this.InterpolantFactoryMethodLinear;break;case go:e=this.InterpolantFactoryMethodSmooth;break;case Ic:e=this.InterpolantFactoryMethodBezier;break}if(e===void 0){let n="unsupported interpolation for "+this.ValueTypeName+" keyframe track named "+this.name;if(this.createInterpolant===void 0)if(t!==this.DefaultInterpolation)this.setInterpolation(this.DefaultInterpolation);else throw new Error(n);return Zt("KeyframeTrack:",n),this}return this.createInterpolant=e,this}getInterpolation(){switch(this.createInterpolant){case this.InterpolantFactoryMethodDiscrete:return ca;case this.InterpolantFactoryMethodLinear:return To;case this.InterpolantFactoryMethodSmooth:return go;case this.InterpolantFactoryMethodBezier:return Ic}}getValueSize(){return this.values.length/this.times.length}shift(t){if(t!==0){let e=this.times;for(let n=0,s=e.length;n!==s;++n)e[n]+=t}return this}scale(t){if(t!==1){let e=this.times;for(let n=0,s=e.length;n!==s;++n)e[n]*=t;Cc(this.settings)&&(Mu(this.settings.inTangents,t),Mu(this.settings.outTangents,t))}return this}trim(t,e){let n=this.times,s=n.length,r=0,a=s-1;for(;r!==s&&n[r]<t;)++r;for(;a!==-1&&n[a]>e;)--a;if(++a,r!==0||a!==s){r>=a&&(a=Math.max(a,1),r=a-1);let l=this.getValueSize();this.times=n.slice(r,a),this.values=this.values.slice(r*l,a*l)}return this}validate(){let t=!0,e=this.getValueSize();e-Math.floor(e)!==0&&(Kt("KeyframeTrack: Invalid value size in track.",this),t=!1);let n=this.times,s=this.values,r=n.length;r===0&&(Kt("KeyframeTrack: Track is empty.",this),t=!1);let a=null;for(let l=0;l!==r;l++){let o=n[l];if(typeof o=="number"&&isNaN(o)){Kt("KeyframeTrack: Time is not a valid number.",this,l,o),t=!1;break}if(a!==null&&a>o){Kt("KeyframeTrack: Out of order keys.",this,l,o,a),t=!1;break}a=o}if(s!==void 0&&Vf(s))for(let l=0,o=s.length;l!==o;++l){let c=s[l];if(isNaN(c)){Kt("KeyframeTrack: Value is not a valid number.",this,l,c),t=!1;break}}return t}optimize(){let t=this.times.slice(),e=this.values.slice(),n=this.getValueSize(),s=this.getInterpolation()===go,r=t.length-1,a=1;for(let l=1;l<r;++l){let o=!1,c=t[l],h=t[l+1];if(c!==h&&(l!==1||c!==t[0]))if(s)o=!0;else{let f=l*n,d=f-n,p=f+n;for(let x=0;x!==n;++x){let M=e[f+x];if(M!==e[d+x]||M!==e[p+x]){o=!0;break}}}if(o){if(l!==a){t[a]=t[l];let f=l*n,d=a*n;for(let p=0;p!==n;++p)e[d+p]=e[f+p]}++a}}if(r>0){t[a]=t[r];for(let l=r*n,o=a*n,c=0;c!==n;++c)e[o+c]=e[l+c];++a}return a!==t.length?(this.times=t.slice(0,a),this.values=e.slice(0,a*n)):(this.times=t,this.values=e),this}clone(){let t=this.times.slice(),e=this.values.slice(),n=this.constructor,s=new n(this.name,t,e);return s.createInterpolant=this.createInterpolant,Cc(this.settings)&&(s.settings={inTangents:this.settings.inTangents.slice(),outTangents:this.settings.outTangents.slice()}),s}};function Mu(i,t){for(let e=0,n=i.length;e!==n;e+=2)i[e]*=t}Gn.prototype.ValueTypeName="";Gn.prototype.TimeBufferType=Float32Array;Gn.prototype.ValueBufferType=Float32Array;Gn.prototype.DefaultInterpolation=To;var gs=class extends Gn{constructor(t,e,n){super(t,e,n)}};gs.prototype.ValueTypeName="bool";gs.prototype.ValueBufferType=Array;gs.prototype.DefaultInterpolation=ca;gs.prototype.InterpolantFactoryMethodLinear=void 0;gs.prototype.InterpolantFactoryMethodSmooth=void 0;var Bo=class extends Gn{constructor(t,e,n,s){super(t,e,n,s)}};Bo.prototype.ValueTypeName="color";var ko=class extends Gn{constructor(t,e,n,s){super(t,e,n,s)}};ko.prototype.ValueTypeName="number";var Ho=class extends ms{constructor(t,e,n,s){super(t,e,n,s)}interpolate_(t,e,n,s){let r=this.resultBuffer,a=this.sampleValues,l=this.valueSize,o=(n-e)/(s-e),c=t*l;for(let h=c+l;c!==h;c+=4)Ye.slerpFlat(r,0,a,c-l,a,c,o);return r}},Sa=class extends Gn{constructor(t,e,n,s){super(t,e,n,s)}InterpolantFactoryMethodLinear(t){return new Ho(this.times,this.values,this.getValueSize(),t)}};Sa.prototype.ValueTypeName="quaternion";Sa.prototype.InterpolantFactoryMethodSmooth=void 0;var xs=class extends Gn{constructor(t,e,n){super(t,e,n)}};xs.prototype.ValueTypeName="string";xs.prototype.ValueBufferType=Array;xs.prototype.DefaultInterpolation=ca;xs.prototype.InterpolantFactoryMethodLinear=void 0;xs.prototype.InterpolantFactoryMethodSmooth=void 0;var Vo=class extends Gn{constructor(t,e,n,s){super(t,e,n,s)}};Vo.prototype.ValueTypeName="vector";var Go=class{constructor(t,e,n){let s=this,r=!1,a=0,l=0,o,c=[];this.onStart=void 0,this.onLoad=t,this.onProgress=e,this.onError=n,this._abortController=null,this.itemStart=function(h){l++,r===!1&&s.onStart!==void 0&&s.onStart(h,a,l),r=!0},this.itemEnd=function(h){a++,s.onProgress!==void 0&&s.onProgress(h,a,l),a===l&&(r=!1,s.onLoad!==void 0&&s.onLoad())},this.itemError=function(h){s.onError!==void 0&&s.onError(h)},this.resolveURL=function(h){return h=h.normalize("NFC"),o?o(h):h},this.setURLModifier=function(h){return o=h,this},this.addHandler=function(h,f){return c.push(h,f),this},this.removeHandler=function(h){let f=c.indexOf(h);return f!==-1&&c.splice(f,2),this},this.getHandler=function(h){for(let f=0,d=c.length;f<d;f+=2){let p=c[f],x=c[f+1];if(p.global&&(p.lastIndex=0),p.test(h))return x}return null},this.abort=function(){return this.abortController.abort(),this._abortController=null,this}}get abortController(){return this._abortController||(this._abortController=new AbortController),this._abortController}},gd=new Go,Wo=class{constructor(t){this.manager=t!==void 0?t:gd,this.crossOrigin="anonymous",this.withCredentials=!1,this.path="",this.resourcePath="",this.requestHeader={},typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}load(){}loadAsync(t,e){let n=this;return new Promise(function(s,r){n.load(t,s,e,r)})}parse(){}setCrossOrigin(t){return this.crossOrigin=t,this}setWithCredentials(t){return this.withCredentials=t,this}setPath(t){return this.path=t,this}setResourcePath(t){return this.resourcePath=t,this}setRequestHeader(t){return this.requestHeader=t,this}abort(){return this}};Wo.DEFAULT_MATERIAL_NAME="__DEFAULT";var Lr=class extends on{constructor(t,e=1){super(),this.isLight=!0,this.type="Light",this.color=new $t(t),this.intensity=e}copy(t,e){return super.copy(t,e),this.color.copy(t.color),this.intensity=t.intensity,this}toJSON(t){let e=super.toJSON(t);return e.object.color=this.color.getHex(),e.object.intensity=this.intensity,e}},Gs=class extends Lr{constructor(t,e,n){super(t,n),this.isHemisphereLight=!0,this.type="HemisphereLight",this.position.copy(on.DEFAULT_UP),this.updateMatrix(),this.groundColor=new $t(e)}copy(t,e){return super.copy(t,e),this.groundColor.copy(t.groundColor),this}toJSON(t){let e=super.toJSON(t);return e.object.groundColor=this.groundColor.getHex(),e}},Pc=new ge,Su=new F,Eu=new F,Ea=class{constructor(t){this.camera=t,this.intensity=1,this.bias=0,this.biasNode=null,this.normalBias=0,this.radius=1,this.blurSamples=8,this.mapSize=new Xt(512,512),this.mapType=Dn,this.map=null,this.mapPass=null,this.matrix=new ge,this.autoUpdate=!0,this.needsUpdate=!1,this._frustum=new Pr,this._frameExtents=new Xt(1,1),this._viewportCount=1,this._viewports=[new ke(0,0,1,1)]}getViewportCount(){return this._viewportCount}getCamera(){return this.camera}getFrustum(){return this._frustum}updateMatrices(t){let e=this.camera;Su.setFromMatrixPosition(t.matrixWorld),e.position.copy(Su),Eu.setFromMatrixPosition(t.target.matrixWorld),e.lookAt(Eu),e.updateMatrixWorld(),this._updateMatrix(e,this.matrix,this._frustum)}_updateMatrix(t,e,n,s){Pc.multiplyMatrices(t.projectionMatrix,t.matrixWorldInverse),n.setFromProjectionMatrix(Pc,t.coordinateSystem,t.reversedDepth);let r=this._frameExtents,a=s?s.z/r.x:1,l=s?s.w/r.y:1,o=s?s.x/r.x:0,c=s?s.y/r.y:0;t.coordinateSystem===Sr||t.reversedDepth?e.set(.5*a,0,0,.5*a+o,0,.5*l,0,.5*l+c,0,0,1,0,0,0,0,1):e.set(.5*a,0,0,.5*a+o,0,.5*l,0,.5*l+c,0,0,.5,.5,0,0,0,1),e.multiply(Pc)}getViewport(t){return this._viewports[t]}getFrameExtents(){return this._frameExtents}dispose(){this.map&&this.map.dispose(),this.mapPass&&this.mapPass.dispose()}copy(t){return this.camera=t.camera.clone(),this.intensity=t.intensity,this.bias=t.bias,this.radius=t.radius,this.autoUpdate=t.autoUpdate,this.needsUpdate=t.needsUpdate,this.normalBias=t.normalBias,this.blurSamples=t.blurSamples,this.mapSize.copy(t.mapSize),this.biasNode=t.biasNode,this}clone(){return new this.constructor().copy(this)}toJSON(){let t={};return t.intensity=this.intensity,t.bias=this.bias,t.normalBias=this.normalBias,t.radius=this.radius,t.blurSamples=this.blurSamples,t.mapSize=this.mapSize.toArray(),t.camera=this.camera.toJSON(!1).object,delete t.camera.matrix,t}},po=new F,mo=new Ye,bi=new F,wa=class extends on{constructor(){super(),this.isCamera=!0,this.type="Camera",this.matrixWorldInverse=new ge,this.projectionMatrix=new ge,this.projectionMatrixInverse=new ge,this.coordinateSystem=li,this._reversedDepth=!1}get reversedDepth(){return this._reversedDepth}copy(t,e){return super.copy(t,e),this.matrixWorldInverse.copy(t.matrixWorldInverse),this.projectionMatrix.copy(t.projectionMatrix),this.projectionMatrixInverse.copy(t.projectionMatrixInverse),this.coordinateSystem=t.coordinateSystem,this}getWorldDirection(t){return super.getWorldDirection(t).negate()}updateMatrixWorld(t){super.updateMatrixWorld(t),this.matrixWorld.decompose(po,mo,bi),bi.x===1&&bi.y===1&&bi.z===1?this.matrixWorldInverse.copy(this.matrixWorld).invert():this.matrixWorldInverse.compose(po,mo,bi.set(1,1,1)).invert()}updateWorldMatrix(t,e,n=!1){super.updateWorldMatrix(t,e,n),this.matrixWorld.decompose(po,mo,bi),bi.x===1&&bi.y===1&&bi.z===1?this.matrixWorldInverse.copy(this.matrixWorld).invert():this.matrixWorldInverse.compose(po,mo,bi.set(1,1,1)).invert()}clone(){return new this.constructor().copy(this)}},hs=new F,wu=new Xt,Tu=new Xt,Je=class extends wa{constructor(t=50,e=1,n=.1,s=2e3){super(),this.isPerspectiveCamera=!0,this.type="PerspectiveCamera",this.fov=t,this.zoom=1,this.near=n,this.far=s,this.focus=10,this.aspect=e,this.view=null,this.filmGauge=35,this.filmOffset=0,this.updateProjectionMatrix()}copy(t,e){return super.copy(t,e),this.fov=t.fov,this.zoom=t.zoom,this.near=t.near,this.far=t.far,this.focus=t.focus,this.aspect=t.aspect,this.view=t.view===null?null:Object.assign({},t.view),this.filmGauge=t.filmGauge,this.filmOffset=t.filmOffset,this}setFocalLength(t){let e=.5*this.getFilmHeight()/t;this.fov=wr*2*Math.atan(e),this.updateProjectionMatrix()}getFocalLength(){let t=Math.tan(oa*.5*this.fov);return .5*this.getFilmHeight()/t}getEffectiveFOV(){return wr*2*Math.atan(Math.tan(oa*.5*this.fov)/this.zoom)}getFilmWidth(){return this.filmGauge*Math.min(this.aspect,1)}getFilmHeight(){return this.filmGauge/Math.max(this.aspect,1)}getViewBounds(t,e,n){hs.set(-1,-1,.5).applyMatrix4(this.projectionMatrixInverse),e.set(hs.x,hs.y).multiplyScalar(-t/hs.z),hs.set(1,1,.5).applyMatrix4(this.projectionMatrixInverse),n.set(hs.x,hs.y).multiplyScalar(-t/hs.z)}getViewSize(t,e){return this.getViewBounds(t,wu,Tu),e.subVectors(Tu,wu)}setViewOffset(t,e,n,s,r,a){this.aspect=t/e,this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=t,this.view.fullHeight=e,this.view.offsetX=n,this.view.offsetY=s,this.view.width=r,this.view.height=a,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){let t=this.near,e=t*Math.tan(oa*.5*this.fov)/this.zoom,n=2*e,s=this.aspect*n,r=-.5*s,a=this.view;if(this.view!==null&&this.view.enabled){let o=a.fullWidth,c=a.fullHeight;r+=a.offsetX*s/o,e-=a.offsetY*n/c,s*=a.width/o,n*=a.height/c}let l=this.filmOffset;l!==0&&(r+=t*l/this.getFilmWidth()),this.projectionMatrix.makePerspective(r,r+s,e,e-n,t,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(t){let e=super.toJSON(t);return e.object.fov=this.fov,e.object.zoom=this.zoom,e.object.near=this.near,e.object.far=this.far,e.object.focus=this.focus,e.object.aspect=this.aspect,this.view!==null&&(e.object.view=Object.assign({},this.view)),e.object.filmGauge=this.filmGauge,e.object.filmOffset=this.filmOffset,e}};var Nc=class extends Ea{constructor(){super(new Je(90,1,.5,500)),this.isPointLightShadow=!0}},Ti=class extends Lr{constructor(t,e,n=0,s=2){super(t,e),this.isPointLight=!0,this.type="PointLight",this.distance=n,this.decay=s,this.shadow=new Nc}get power(){return this.intensity*4*Math.PI}set power(t){this.intensity=t/(4*Math.PI)}dispose(){super.dispose(),this.shadow.dispose()}copy(t,e){return super.copy(t,e),this.distance=t.distance,this.decay=t.decay,this.shadow=t.shadow.clone(),this}toJSON(t){let e=super.toJSON(t);return e.object.distance=this.distance,e.object.decay=this.decay,e.object.shadow=this.shadow.toJSON(),e}},zr=class extends wa{constructor(t=-1,e=1,n=1,s=-1,r=.1,a=2e3){super(),this.isOrthographicCamera=!0,this.type="OrthographicCamera",this.zoom=1,this.view=null,this.left=t,this.right=e,this.top=n,this.bottom=s,this.near=r,this.far=a,this.updateProjectionMatrix()}copy(t,e){return super.copy(t,e),this.left=t.left,this.right=t.right,this.top=t.top,this.bottom=t.bottom,this.near=t.near,this.far=t.far,this.zoom=t.zoom,this.view=t.view===null?null:Object.assign({},t.view),this}setViewOffset(t,e,n,s,r,a){this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=t,this.view.fullHeight=e,this.view.offsetX=n,this.view.offsetY=s,this.view.width=r,this.view.height=a,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){let t=(this.right-this.left)/(2*this.zoom),e=(this.top-this.bottom)/(2*this.zoom),n=(this.right+this.left)/2,s=(this.top+this.bottom)/2,r=n-t,a=n+t,l=s+e,o=s-e;if(this.view!==null&&this.view.enabled){let c=(this.right-this.left)/this.view.fullWidth/this.zoom,h=(this.top-this.bottom)/this.view.fullHeight/this.zoom;r+=c*this.view.offsetX,a=r+c*this.view.width,l-=h*this.view.offsetY,o=l-h*this.view.height}this.projectionMatrix.makeOrthographic(r,a,l,o,this.near,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(t){let e=super.toJSON(t);return e.object.zoom=this.zoom,e.object.left=this.left,e.object.right=this.right,e.object.top=this.top,e.object.bottom=this.bottom,e.object.near=this.near,e.object.far=this.far,this.view!==null&&(e.object.view=Object.assign({},this.view)),e}},Uc=class extends Ea{constructor(){super(new zr(-5,5,5,-5,.5,500)),this.isDirectionalLightShadow=!0}},Yi=class extends Lr{constructor(t,e){super(t,e),this.isDirectionalLight=!0,this.type="DirectionalLight",this.position.copy(on.DEFAULT_UP),this.updateMatrix(),this.target=new on,this.shadow=new Uc}dispose(){super.dispose(),this.shadow.dispose()}copy(t){return super.copy(t),this.target=t.target.clone(),this.shadow=t.shadow.clone(),this}toJSON(t){let e=super.toJSON(t);return e.object.shadow=this.shadow.toJSON(),e.object.target=this.target.uuid,e}};var _r=-90,yr=1,Xo=class extends on{constructor(t,e,n){super(),this.type="CubeCamera",this.renderTarget=n,this.coordinateSystem=null,this.activeMipmapLevel=0;let s=new Je(_r,yr,t,e);s.layers=this.layers,this.add(s);let r=new Je(_r,yr,t,e);r.layers=this.layers,this.add(r);let a=new Je(_r,yr,t,e);a.layers=this.layers,this.add(a);let l=new Je(_r,yr,t,e);l.layers=this.layers,this.add(l);let o=new Je(_r,yr,t,e);o.layers=this.layers,this.add(o);let c=new Je(_r,yr,t,e);c.layers=this.layers,this.add(c)}updateCoordinateSystem(){let t=this.coordinateSystem,e=this.children.concat(),[n,s,r,a,l,o]=e;for(let c of e)this.remove(c);if(t===li)n.up.set(0,1,0),n.lookAt(1,0,0),s.up.set(0,1,0),s.lookAt(-1,0,0),r.up.set(0,0,-1),r.lookAt(0,1,0),a.up.set(0,0,1),a.lookAt(0,-1,0),l.up.set(0,1,0),l.lookAt(0,0,1),o.up.set(0,1,0),o.lookAt(0,0,-1);else if(t===Sr)n.up.set(0,-1,0),n.lookAt(-1,0,0),s.up.set(0,-1,0),s.lookAt(1,0,0),r.up.set(0,0,1),r.lookAt(0,1,0),a.up.set(0,0,-1),a.lookAt(0,-1,0),l.up.set(0,-1,0),l.lookAt(0,0,1),o.up.set(0,-1,0),o.lookAt(0,0,-1);else throw new Error("THREE.CubeCamera.updateCoordinateSystem(): Invalid coordinate system: "+t);for(let c of e)this.add(c),c.updateMatrixWorld()}update(t,e){this.parent===null&&this.updateMatrixWorld();let{renderTarget:n,activeMipmapLevel:s}=this;this.coordinateSystem!==t.coordinateSystem&&(this.coordinateSystem=t.coordinateSystem,this.updateCoordinateSystem());let[r,a,l,o,c,h]=this.children,f=t.getRenderTarget(),d=t.getActiveCubeFace(),p=t.getActiveMipmapLevel(),x=t.xr.enabled;t.xr.enabled=!1;let M=n.texture.generateMipmaps;n.texture.generateMipmaps=!1;let m=!1;t.isWebGLRenderer===!0?m=t.state.buffers.depth.getReversed():m=t.reversedDepthBuffer,t.setRenderTarget(n,0,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,r),t.setRenderTarget(n,1,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,a),t.setRenderTarget(n,2,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,l),t.setRenderTarget(n,3,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,o),t.setRenderTarget(n,4,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,c),n.texture.generateMipmaps=M,t.setRenderTarget(n,5,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,h),t.setRenderTarget(f,d,p),t.xr.enabled=x,n.texture.needsPMREMUpdate=!0}},qo=class extends Je{constructor(t=[]){super(),this.isArrayCamera=!0,this.isMultiViewCamera=!1,this.cameras=t}};var hh="\\[\\]\\.:\\/",Cp=new RegExp("["+hh+"]","g"),uh="[^"+hh+"]",Pp="[^"+hh.replace("\\.","")+"]",Ip=/((?:WC+[\/:])*)/.source.replace("WC",uh),Lp=/(WCOD+)?/.source.replace("WCOD",Pp),zp=/(?:\.(WC+)(?:\[(.+)\])?)?/.source.replace("WC",uh),Dp=/\.(WC+)(?:\[(.+)\])?/.source.replace("WC",uh),Np=new RegExp("^"+Ip+Lp+zp+Dp+"$"),Up=["material","materials","bones","map"],Fc=class{constructor(t,e,n){let s=n||Fe.parseTrackName(e);this._targetGroup=t,this._bindings=t.subscribe_(e,s)}getValue(t,e){this.bind();let n=this._targetGroup.nCachedObjects_,s=this._bindings[n];s!==void 0&&s.getValue(t,e)}setValue(t,e){let n=this._bindings;for(let s=this._targetGroup.nCachedObjects_,r=n.length;s!==r;++s)n[s].setValue(t,e)}bind(){let t=this._bindings;for(let e=this._targetGroup.nCachedObjects_,n=t.length;e!==n;++e)t[e].bind()}unbind(){let t=this._bindings;for(let e=this._targetGroup.nCachedObjects_,n=t.length;e!==n;++e)t[e].unbind()}},Fe=class i{constructor(t,e,n){this.path=e,this.parsedPath=n||i.parseTrackName(e),this.node=i.findNode(t,this.parsedPath.nodeName),this.rootNode=t,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}static create(t,e,n){return t&&t.isAnimationObjectGroup?new i.Composite(t,e,n):new i(t,e,n)}static sanitizeNodeName(t){return t.replace(/\s/g,"_").replace(Cp,"")}static parseTrackName(t){let e=Np.exec(t);if(e===null)throw new Error("THREE.PropertyBinding: Cannot parse trackName: "+t);let n={nodeName:e[2],objectName:e[3],objectIndex:e[4],propertyName:e[5],propertyIndex:e[6]},s=n.nodeName&&n.nodeName.lastIndexOf(".");if(s!==void 0&&s!==-1){let r=n.nodeName.substring(s+1);Up.indexOf(r)!==-1&&(n.nodeName=n.nodeName.substring(0,s),n.objectName=r)}if(n.propertyName===null||n.propertyName.length===0)throw new Error("THREE.PropertyBinding: can not parse propertyName from trackName: "+t);return n}static findNode(t,e){if(e===void 0||e===""||e==="."||e===-1||e===t.name||e===t.uuid)return t;if(t.skeleton){let n=t.skeleton.getBoneByName(e);if(n!==void 0)return n}if(t.children){let n=function(r){for(let a=0;a<r.length;a++){let l=r[a];if(l.name===e||l.uuid===e)return l;let o=n(l.children);if(o)return o}return null},s=n(t.children);if(s)return s}return null}_getValue_unavailable(){}_setValue_unavailable(){}_getValue_direct(t,e){t[e]=this.targetObject[this.propertyName]}_getValue_array(t,e){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)t[e++]=n[s]}_getValue_arrayElement(t,e){t[e]=this.resolvedProperty[this.propertyIndex]}_getValue_toArray(t,e){this.resolvedProperty.toArray(t,e)}_setValue_direct(t,e){this.targetObject[this.propertyName]=t[e]}_setValue_direct_setNeedsUpdate(t,e){this.targetObject[this.propertyName]=t[e],this.targetObject.needsUpdate=!0}_setValue_direct_setMatrixWorldNeedsUpdate(t,e){this.targetObject[this.propertyName]=t[e],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_array(t,e){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)n[s]=t[e++]}_setValue_array_setNeedsUpdate(t,e){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)n[s]=t[e++];this.targetObject.needsUpdate=!0}_setValue_array_setMatrixWorldNeedsUpdate(t,e){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)n[s]=t[e++];this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_arrayElement(t,e){this.resolvedProperty[this.propertyIndex]=t[e]}_setValue_arrayElement_setNeedsUpdate(t,e){this.resolvedProperty[this.propertyIndex]=t[e],this.targetObject.needsUpdate=!0}_setValue_arrayElement_setMatrixWorldNeedsUpdate(t,e){this.resolvedProperty[this.propertyIndex]=t[e],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_fromArray(t,e){this.resolvedProperty.fromArray(t,e)}_setValue_fromArray_setNeedsUpdate(t,e){this.resolvedProperty.fromArray(t,e),this.targetObject.needsUpdate=!0}_setValue_fromArray_setMatrixWorldNeedsUpdate(t,e){this.resolvedProperty.fromArray(t,e),this.targetObject.matrixWorldNeedsUpdate=!0}_getValue_unbound(t,e){this.bind(),this.getValue(t,e)}_setValue_unbound(t,e){this.bind(),this.setValue(t,e)}bind(){let t=this.node,e=this.parsedPath,n=e.objectName,s=e.propertyName,r=e.propertyIndex;if(t||(t=i.findNode(this.rootNode,e.nodeName),this.node=t),this.getValue=this._getValue_unavailable,this.setValue=this._setValue_unavailable,!t){Zt("PropertyBinding: No target node found for track: "+this.path+".");return}if(n){let c=e.objectIndex;switch(n){case"materials":if(!t.material){Kt("PropertyBinding: Can not bind to material as node does not have a material.",this);return}if(!t.material.materials){Kt("PropertyBinding: Can not bind to material.materials as node.material does not have a materials array.",this);return}t=t.material.materials;break;case"bones":if(!t.skeleton){Kt("PropertyBinding: Can not bind to bones as node does not have a skeleton.",this);return}t=t.skeleton.bones;for(let h=0;h<t.length;h++)if(t[h].name===c){c=h;break}break;case"map":if("map"in t){t=t.map;break}if(!t.material){Kt("PropertyBinding: Can not bind to material as node does not have a material.",this);return}if(!t.material.map){Kt("PropertyBinding: Can not bind to material.map as node.material does not have a map.",this);return}t=t.material.map;break;default:if(t[n]===void 0){Kt("PropertyBinding: Can not bind to objectName of node undefined.",this);return}t=t[n]}if(c!==void 0){if(t[c]===void 0){Kt("PropertyBinding: Trying to bind to objectIndex of objectName, but is undefined.",this,t);return}t=t[c]}}let a=t[s];if(a===void 0){let c=e.nodeName;Kt("PropertyBinding: Trying to update property for track: "+c+"."+s+" but it wasn't found.",t);return}let l=this.Versioning.None;this.targetObject=t,t.isMaterial===!0?l=this.Versioning.NeedsUpdate:t.isObject3D===!0&&(l=this.Versioning.MatrixWorldNeedsUpdate);let o=this.BindingType.Direct;if(r!==void 0){if(s==="morphTargetInfluences"){if(!t.geometry){Kt("PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.",this);return}if(!t.geometry.morphAttributes){Kt("PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.morphAttributes.",this);return}t.morphTargetDictionary[r]!==void 0&&(r=t.morphTargetDictionary[r])}o=this.BindingType.ArrayElement,this.resolvedProperty=a,this.propertyIndex=r}else a.fromArray!==void 0&&a.toArray!==void 0?(o=this.BindingType.HasFromToArray,this.resolvedProperty=a):Array.isArray(a)?(o=this.BindingType.EntireArray,this.resolvedProperty=a):this.propertyName=s;this.getValue=this.GetterByBindingType[o],this.setValue=this.SetterByBindingTypeAndVersioning[o][l]}unbind(){this.node=null,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}};Fe.Composite=Fc;Fe.prototype.BindingType={Direct:0,EntireArray:1,ArrayElement:2,HasFromToArray:3};Fe.prototype.Versioning={None:0,NeedsUpdate:1,MatrixWorldNeedsUpdate:2};Fe.prototype.GetterByBindingType=[Fe.prototype._getValue_direct,Fe.prototype._getValue_array,Fe.prototype._getValue_arrayElement,Fe.prototype._getValue_toArray];Fe.prototype.SetterByBindingTypeAndVersioning=[[Fe.prototype._setValue_direct,Fe.prototype._setValue_direct_setNeedsUpdate,Fe.prototype._setValue_direct_setMatrixWorldNeedsUpdate],[Fe.prototype._setValue_array,Fe.prototype._setValue_array_setNeedsUpdate,Fe.prototype._setValue_array_setMatrixWorldNeedsUpdate],[Fe.prototype._setValue_arrayElement,Fe.prototype._setValue_arrayElement_setNeedsUpdate,Fe.prototype._setValue_arrayElement_setMatrixWorldNeedsUpdate],[Fe.prototype._setValue_fromArray,Fe.prototype._setValue_fromArray_setNeedsUpdate,Fe.prototype._setValue_fromArray_setMatrixWorldNeedsUpdate]];var jy=new Float32Array(1);var Au=new ge,Ws=class{constructor(t,e,n=0,s=1/0){this.ray=new ks(t,e),this.near=n,this.far=s,this.camera=null,this.layers=new Ar,this.params={Mesh:{},Line:{threshold:1},LOD:{},Points:{threshold:1},Sprite:{}}}set(t,e){this.ray.set(t,e)}setFromCamera(t,e){e.isPerspectiveCamera?(this.ray.origin.setFromMatrixPosition(e.matrixWorld),this.ray.direction.set(t.x,t.y,.5).unproject(e).sub(this.ray.origin).normalize(),this.camera=e):e.isOrthographicCamera?(this.ray.origin.set(t.x,t.y,e.projectionMatrix.elements[14]).unproject(e),this.ray.direction.set(0,0,-1).transformDirection(e.matrixWorld),this.camera=e):Kt("Raycaster: Unsupported camera type: "+e.type)}setFromXRController(t){return Au.identity().extractRotation(t.matrixWorld),this.ray.origin.setFromMatrixPosition(t.matrixWorld),this.ray.direction.set(0,0,-1).applyMatrix4(Au),this}intersectObject(t,e=!0,n=[]){return Oc(t,this,n,e),n.sort(Ru),n}intersectObjects(t,e=!0,n=[]){for(let s=0,r=t.length;s<r;s++)Oc(t[s],this,n,e);return n.sort(Ru),n}};function Ru(i,t){return i.distance-t.distance}function Oc(i,t,e,n){let s=!0;if(i.layers.test(t.layers)&&i.raycast(t,e)===!1&&(s=!1),s===!0&&n===!0){let r=i.children;for(let a=0,l=r.length;a<l;a++)Oc(r[a],t,e,!0)}}var zn=class{constructor(t=1,e=0,n=0){this.radius=t,this.phi=e,this.theta=n}set(t,e,n){return this.radius=t,this.phi=e,this.theta=n,this}copy(t){return this.radius=t.radius,this.phi=t.phi,this.theta=t.theta,this}makeSafe(){return this.phi=de(this.phi,1e-6,Math.PI-1e-6),this}setFromVector3(t){return this.setFromCartesianCoords(t.x,t.y,t.z)}setFromCartesianCoords(t,e,n){return this.radius=Math.sqrt(t*t+e*e+n*n),this.radius===0?(this.theta=0,this.phi=0):(this.theta=Math.atan2(t,n),this.phi=Math.acos(de(e/this.radius,-1,1))),this}clone(){return new this.constructor().copy(this)}};var xh=class xh{constructor(t,e,n,s){this.elements=[1,0,0,1],t!==void 0&&this.set(t,e,n,s)}identity(){return this.set(1,0,0,1),this}fromArray(t,e=0){for(let n=0;n<4;n++)this.elements[n]=t[n+e];return this}set(t,e,n,s){let r=this.elements;return r[0]=t,r[2]=e,r[1]=n,r[3]=s,this}};xh.prototype.isMatrix2=!0;var Bc=xh;var Ta=class extends ci{constructor(t,e=null){super(),this.object=t,this.domElement=e,this.enabled=!0,this.state=-1,this.keys={},this.mouseButtons={LEFT:null,MIDDLE:null,RIGHT:null},this.touches={ONE:null,TWO:null}}connect(t){this.domElement!==null&&this.disconnect(),this.domElement=t}disconnect(){}dispose(){}update(){}};function dh(i,t,e,n){let s=Fp(n);switch(e){case sh:return i*t;case tl:return i*t/s.components*s.byteLength;case el:return i*t/s.components*s.byteLength;case Es:return i*t*2/s.components*s.byteLength;case nl:return i*t*2/s.components*s.byteLength;case rh:return i*t*3/s.components*s.byteLength;case $n:return i*t*4/s.components*s.byteLength;case il:return i*t*4/s.components*s.byteLength;case Ca:case Pa:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*8;case Ia:case La:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*16;case rl:case ol:return Math.max(i,16)*Math.max(t,8)/4;case sl:case al:return Math.max(i,8)*Math.max(t,8)/2;case ll:case cl:case ul:case dl:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*8;case hl:case za:case fl:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*16;case pl:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*16;case ml:return Math.floor((i+4)/5)*Math.floor((t+3)/4)*16;case gl:return Math.floor((i+4)/5)*Math.floor((t+4)/5)*16;case xl:return Math.floor((i+5)/6)*Math.floor((t+4)/5)*16;case _l:return Math.floor((i+5)/6)*Math.floor((t+5)/6)*16;case yl:return Math.floor((i+7)/8)*Math.floor((t+4)/5)*16;case vl:return Math.floor((i+7)/8)*Math.floor((t+5)/6)*16;case bl:return Math.floor((i+7)/8)*Math.floor((t+7)/8)*16;case Ml:return Math.floor((i+9)/10)*Math.floor((t+4)/5)*16;case Sl:return Math.floor((i+9)/10)*Math.floor((t+5)/6)*16;case El:return Math.floor((i+9)/10)*Math.floor((t+7)/8)*16;case wl:return Math.floor((i+9)/10)*Math.floor((t+9)/10)*16;case Tl:return Math.floor((i+11)/12)*Math.floor((t+9)/10)*16;case Al:return Math.floor((i+11)/12)*Math.floor((t+11)/12)*16;case Rl:case Cl:case Pl:return Math.ceil(i/4)*Math.ceil(t/4)*16;case Il:case Ll:return Math.ceil(i/4)*Math.ceil(t/4)*8;case Da:case zl:return Math.ceil(i/4)*Math.ceil(t/4)*16}throw new Error(`Unable to determine texture byte length for ${e} format.`)}function Fp(i){switch(i){case Dn:case th:return{byteLength:1,components:1};case Ur:case eh:case fi:return{byteLength:2,components:1};case jo:case Qo:return{byteLength:2,components:4};case di:case Jo:case Zn:return{byteLength:4,components:1};case nh:case ih:return{byteLength:4,components:3}}throw new Error(`THREE.TextureUtils: Unknown texture type ${i}.`)}typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("register",{detail:{revision:"186"}}));typeof window<"u"&&(window.__THREE__?Zt("WARNING: Multiple instances of Three.js being imported."):window.__THREE__="186");/**
 * @license
 * Copyright 2010-2026 Three.js Authors
 * SPDX-License-Identifier: MIT
 */function Od(){let i=null,t=!1,e=null,n=null;function s(r,a){n=i.requestAnimationFrame(s),e(r,a)}return{start:function(){t!==!0&&e!==null&&i!==null&&(n=i.requestAnimationFrame(s),t=!0)},stop:function(){i!==null&&i.cancelAnimationFrame(n),t=!1},setAnimationLoop:function(r){e=r},setContext:function(r){i=r}}}function Wp(i){let t=new WeakMap;function e(l,o){let c=l.array,h=l.usage,f=c.byteLength,d=i.createBuffer();i.bindBuffer(o,d),i.bufferData(o,c,h),l.onUploadCallback();let p;if(c instanceof Float32Array)p=i.FLOAT;else if(typeof Float16Array<"u"&&c instanceof Float16Array)p=i.HALF_FLOAT;else if(c instanceof Uint16Array)l.isFloat16BufferAttribute?p=i.HALF_FLOAT:p=i.UNSIGNED_SHORT;else if(c instanceof Int16Array)p=i.SHORT;else if(c instanceof Uint32Array)p=i.UNSIGNED_INT;else if(c instanceof Int32Array)p=i.INT;else if(c instanceof Int8Array)p=i.BYTE;else if(c instanceof Uint8Array)p=i.UNSIGNED_BYTE;else if(c instanceof Uint8ClampedArray)p=i.UNSIGNED_BYTE;else throw new Error("THREE.WebGLAttributes: Unsupported buffer data format: "+c);return{buffer:d,type:p,bytesPerElement:c.BYTES_PER_ELEMENT,version:l.version,size:f}}function n(l,o,c){let h=o.array,f=o.updateRanges;if(i.bindBuffer(c,l),f.length===0)i.bufferSubData(c,0,h);else{f.sort((p,x)=>p.start-x.start);let d=0;for(let p=1;p<f.length;p++){let x=f[d],M=f[p];M.start<=x.start+x.count+1?x.count=Math.max(x.count,M.start+M.count-x.start):(++d,f[d]=M)}f.length=d+1;for(let p=0,x=f.length;p<x;p++){let M=f[p];i.bufferSubData(c,M.start*h.BYTES_PER_ELEMENT,h,M.start,M.count)}o.clearUpdateRanges()}o.onUploadCallback()}function s(l){return l.isInterleavedBufferAttribute&&(l=l.data),t.get(l)}function r(l){l.isInterleavedBufferAttribute&&(l=l.data);let o=t.get(l);o&&(i.deleteBuffer(o.buffer),t.delete(l))}function a(l,o){if(l.isInterleavedBufferAttribute&&(l=l.data),l.isGLBufferAttribute){let h=t.get(l);(!h||h.version<l.version)&&t.set(l,{buffer:l.buffer,type:l.type,bytesPerElement:l.elementSize,version:l.version});return}let c=t.get(l);if(c===void 0)t.set(l,e(l,o));else if(c.version<l.version){if(c.size!==l.array.byteLength)throw new Error("THREE.WebGLAttributes: The size of the buffer attribute's array buffer does not match the original size. Resizing buffer attributes is not supported.");n(c.buffer,l,o),c.version=l.version}}return{get:s,remove:r,update:a}}var Xp=`#ifdef USE_ALPHAHASH
	if ( diffuseColor.a < getAlphaHashThreshold( vPosition ) ) discard;
#endif`,qp=`#ifdef USE_ALPHAHASH
	const float ALPHA_HASH_SCALE = 0.05;
	float hash2D( vec2 value ) {
		return fract( 1.0e4 * sin( 17.0 * value.x + 0.1 * value.y ) * ( 0.1 + abs( sin( 13.0 * value.y + value.x ) ) ) );
	}
	float hash3D( vec3 value ) {
		return hash2D( vec2( hash2D( value.xy ), value.z ) );
	}
	float getAlphaHashThreshold( vec3 position ) {
		float maxDeriv = max(
			length( dFdx( position.xyz ) ),
			length( dFdy( position.xyz ) )
		);
		float pixScale = 1.0 / ( ALPHA_HASH_SCALE * maxDeriv );
		vec2 pixScales = vec2(
			exp2( floor( log2( pixScale ) ) ),
			exp2( ceil( log2( pixScale ) ) )
		);
		vec2 alpha = vec2(
			hash3D( floor( pixScales.x * position.xyz ) ),
			hash3D( floor( pixScales.y * position.xyz ) )
		);
		float lerpFactor = fract( log2( pixScale ) );
		float x = ( 1.0 - lerpFactor ) * alpha.x + lerpFactor * alpha.y;
		float a = min( lerpFactor, 1.0 - lerpFactor );
		vec3 cases = vec3(
			x * x / ( 2.0 * a * ( 1.0 - a ) ),
			( x - 0.5 * a ) / ( 1.0 - a ),
			1.0 - ( ( 1.0 - x ) * ( 1.0 - x ) / ( 2.0 * a * ( 1.0 - a ) ) )
		);
		float threshold = ( x < ( 1.0 - a ) )
			? ( ( x < a ) ? cases.x : cases.y )
			: cases.z;
		return clamp( threshold , 1.0e-6, 1.0 );
	}
#endif`,Yp=`#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, vAlphaMapUv ).g;
#endif`,Zp=`#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,$p=`#ifdef USE_ALPHATEST
	#ifdef ALPHA_TO_COVERAGE
	diffuseColor.a = smoothstep( alphaTest, alphaTest + fwidth( diffuseColor.a ), diffuseColor.a );
	if ( diffuseColor.a == 0.0 ) discard;
	#else
	if ( diffuseColor.a < alphaTest ) discard;
	#endif
#endif`,Kp=`#ifdef USE_ALPHATEST
	uniform float alphaTest;
#endif`,Jp=`#ifdef USE_AOMAP
	float ambientOcclusion = ( texture2D( aoMap, vAoMapUv ).r - 1.0 ) * aoMapIntensity + 1.0;
	reflectedLight.indirectDiffuse *= ambientOcclusion;
	#if defined( USE_CLEARCOAT ) 
		clearcoatSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_SHEEN ) 
		sheenSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_ENVMAP ) && defined( STANDARD )
		float dotNV = saturate( dot( geometryNormal, geometryViewDir ) );
		reflectedLight.indirectSpecular *= computeSpecularOcclusion( dotNV, ambientOcclusion, material.roughness );
	#endif
#endif`,jp=`#ifdef USE_AOMAP
	uniform sampler2D aoMap;
	uniform float aoMapIntensity;
#endif`,Qp=`#ifdef USE_BATCHING
	#if ! defined( GL_ANGLE_multi_draw )
	#define gl_DrawID _gl_DrawID
	uniform int _gl_DrawID;
	#endif
	uniform highp sampler2D batchingTexture;
	uniform highp usampler2D batchingIdTexture;
	mat4 getBatchingMatrix( const in float i ) {
		int size = textureSize( batchingTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( batchingTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( batchingTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( batchingTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( batchingTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
	float getIndirectIndex( const in int i ) {
		int size = textureSize( batchingIdTexture, 0 ).x;
		int x = i % size;
		int y = i / size;
		return float( texelFetch( batchingIdTexture, ivec2( x, y ), 0 ).r );
	}
#endif
#ifdef USE_BATCHING_COLOR
	uniform sampler2D batchingColorTexture;
	vec4 getBatchingColor( const in float i ) {
		int size = textureSize( batchingColorTexture, 0 ).x;
		int j = int( i );
		int x = j % size;
		int y = j / size;
		return texelFetch( batchingColorTexture, ivec2( x, y ), 0 );
	}
#endif`,tm=`#ifdef USE_BATCHING
	mat4 batchingMatrix = getBatchingMatrix( getIndirectIndex( gl_DrawID ) );
#endif`,em=`vec3 transformed = vec3( position );
#ifdef USE_ALPHAHASH
	vPosition = vec3( position );
#endif`,nm=`vec3 objectNormal = vec3( normal );
#ifdef USE_TANGENT
	vec3 objectTangent = vec3( tangent.xyz );
#endif`,im=`float G_BlinnPhong_Implicit( ) {
	return 0.25;
}
float D_BlinnPhong( const in float shininess, const in float dotNH ) {
	return RECIPROCAL_PI * ( shininess * 0.5 + 1.0 ) * pow( dotNH, shininess );
}
vec3 BRDF_BlinnPhong( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in vec3 specularColor, const in float shininess ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( specularColor, 1.0, dotVH );
	float G = G_BlinnPhong_Implicit( );
	float D = D_BlinnPhong( shininess, dotNH );
	return F * ( G * D );
} // validated`,sm=`#ifdef USE_IRIDESCENCE
	const mat3 XYZ_TO_REC709 = mat3(
		 3.2404542, -0.9692660,  0.0556434,
		-1.5371385,  1.8760108, -0.2040259,
		-0.4985314,  0.0415560,  1.0572252
	);
	vec3 Fresnel0ToIor( vec3 fresnel0 ) {
		vec3 sqrtF0 = sqrt( fresnel0 );
		return ( vec3( 1.0 ) + sqrtF0 ) / ( vec3( 1.0 ) - sqrtF0 );
	}
	vec3 IorToFresnel0( vec3 transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - vec3( incidentIor ) ) / ( transmittedIor + vec3( incidentIor ) ) );
	}
	float IorToFresnel0( float transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - incidentIor ) / ( transmittedIor + incidentIor ));
	}
	vec3 evalSensitivity( float OPD, vec3 shift ) {
		float phase = 2.0 * PI * OPD * 1.0e-9;
		vec3 val = vec3( 5.4856e-13, 4.4201e-13, 5.2481e-13 );
		vec3 pos = vec3( 1.6810e+06, 1.7953e+06, 2.2084e+06 );
		vec3 var = vec3( 4.3278e+09, 9.3046e+09, 6.6121e+09 );
		vec3 xyz = val * sqrt( 2.0 * PI * var ) * cos( pos * phase + shift ) * exp( - pow2( phase ) * var );
		xyz.x += 9.7470e-14 * sqrt( 2.0 * PI * 4.5282e+09 ) * cos( 2.2399e+06 * phase + shift[ 0 ] ) * exp( - 4.5282e+09 * pow2( phase ) );
		xyz /= 1.0685e-7;
		vec3 rgb = XYZ_TO_REC709 * xyz;
		return rgb;
	}
	vec3 evalIridescence( float outsideIOR, float eta2, float cosTheta1, float thinFilmThickness, vec3 baseF0 ) {
		vec3 I;
		float iridescenceIOR = mix( outsideIOR, eta2, smoothstep( 0.0, 0.03, thinFilmThickness ) );
		float sinTheta2Sq = pow2( outsideIOR / iridescenceIOR ) * ( 1.0 - pow2( cosTheta1 ) );
		float cosTheta2Sq = 1.0 - sinTheta2Sq;
		if ( cosTheta2Sq < 0.0 ) {
			return vec3( 1.0 );
		}
		float cosTheta2 = sqrt( cosTheta2Sq );
		float R0 = IorToFresnel0( iridescenceIOR, outsideIOR );
		float R12 = F_Schlick( R0, 1.0, cosTheta1 );
		float T121 = 1.0 - R12;
		float phi12 = 0.0;
		if ( iridescenceIOR < outsideIOR ) phi12 = PI;
		float phi21 = PI - phi12;
		vec3 baseIOR = Fresnel0ToIor( clamp( baseF0, 0.0, 0.9999 ) );		vec3 R1 = IorToFresnel0( baseIOR, iridescenceIOR );
		vec3 R23 = F_Schlick( R1, 1.0, cosTheta2 );
		vec3 phi23 = vec3( 0.0 );
		if ( baseIOR[ 0 ] < iridescenceIOR ) phi23[ 0 ] = PI;
		if ( baseIOR[ 1 ] < iridescenceIOR ) phi23[ 1 ] = PI;
		if ( baseIOR[ 2 ] < iridescenceIOR ) phi23[ 2 ] = PI;
		float OPD = 2.0 * iridescenceIOR * thinFilmThickness * cosTheta2;
		vec3 phi = vec3( phi21 ) + phi23;
		vec3 R123 = clamp( R12 * R23, 1e-5, 0.9999 );
		vec3 r123 = sqrt( R123 );
		vec3 Rs = pow2( T121 ) * R23 / ( vec3( 1.0 ) - R123 );
		vec3 C0 = R12 + Rs;
		I = C0;
		vec3 Cm = Rs - T121;
		for ( int m = 1; m <= 2; ++ m ) {
			Cm *= r123;
			vec3 Sm = 2.0 * evalSensitivity( float( m ) * OPD, float( m ) * phi );
			I += Cm * Sm;
		}
		return max( I, vec3( 0.0 ) );
	}
#endif`,rm=`#ifdef USE_BUMPMAP
	uniform sampler2D bumpMap;
	uniform float bumpScale;
	vec2 dHdxy_fwd() {
		vec2 dSTdx = dFdx( vBumpMapUv );
		vec2 dSTdy = dFdy( vBumpMapUv );
		float Hll = bumpScale * texture2D( bumpMap, vBumpMapUv ).x;
		float dBx = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdx ).x - Hll;
		float dBy = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdy ).x - Hll;
		return vec2( dBx, dBy );
	}
	vec3 perturbNormalArb( vec3 surf_pos, vec3 surf_norm, vec2 dHdxy, float faceDirection ) {
		vec3 vSigmaX = normalize( dFdx( surf_pos.xyz ) );
		vec3 vSigmaY = normalize( dFdy( surf_pos.xyz ) );
		vec3 vN = surf_norm;
		vec3 R1 = cross( vSigmaY, vN );
		vec3 R2 = cross( vN, vSigmaX );
		float fDet = dot( vSigmaX, R1 ) * faceDirection;
		vec3 vGrad = sign( fDet ) * ( dHdxy.x * R1 + dHdxy.y * R2 );
		return normalize( abs( fDet ) * surf_norm - vGrad );
	}
#endif`,am=`#if NUM_CLIPPING_PLANES > 0
	vec4 plane;
	#ifdef ALPHA_TO_COVERAGE
		float distanceToPlane, distanceGradient;
		float clipOpacity = 1.0;
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
			distanceGradient = fwidth( distanceToPlane ) / 2.0;
			clipOpacity *= smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			if ( clipOpacity == 0.0 ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			float unionClipOpacity = 1.0;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
				distanceGradient = fwidth( distanceToPlane ) / 2.0;
				unionClipOpacity *= 1.0 - smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			}
			#pragma unroll_loop_end
			clipOpacity *= 1.0 - unionClipOpacity;
		#endif
		diffuseColor.a *= clipOpacity;
		if ( diffuseColor.a == 0.0 ) discard;
	#else
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			if ( dot( vClipPosition, plane.xyz ) > plane.w ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			bool clipped = true;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				clipped = ( dot( vClipPosition, plane.xyz ) > plane.w ) && clipped;
			}
			#pragma unroll_loop_end
			if ( clipped ) discard;
		#endif
	#endif
#endif`,om=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
	uniform vec4 clippingPlanes[ NUM_CLIPPING_PLANES ];
#endif`,lm=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
#endif`,cm=`#if NUM_CLIPPING_PLANES > 0
	vClipPosition = - mvPosition.xyz;
#endif`,hm=`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )
	diffuseColor *= vColor;
#endif`,um=`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )
	varying vec4 vColor;
#endif`,dm=`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	varying vec4 vColor;
#endif`,fm=`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	vColor = vec4( 1.0 );
#endif
#ifdef USE_COLOR_ALPHA
	vColor *= color;
#elif defined( USE_COLOR )
	vColor.rgb *= color;
#endif
#ifdef USE_INSTANCING_COLOR
	vColor.rgb *= instanceColor.rgb;
#endif
#ifdef USE_BATCHING_COLOR
	vColor *= getBatchingColor( getIndirectIndex( gl_DrawID ) );
#endif`,pm=`#define PI 3.141592653589793
#define PI2 6.283185307179586
#define PI_HALF 1.5707963267948966
#define RECIPROCAL_PI 0.3183098861837907
#define RECIPROCAL_PI2 0.15915494309189535
#define EPSILON 1e-6
#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
#define whiteComplement( a ) ( 1.0 - saturate( a ) )
float pow2( const in float x ) { return x*x; }
vec3 pow2( const in vec3 x ) { return x*x; }
float pow3( const in float x ) { return x*x*x; }
float pow4( const in float x ) { float x2 = x*x; return x2*x2; }
float max3( const in vec3 v ) { return max( max( v.x, v.y ), v.z ); }
float average( const in vec3 v ) { return dot( v, vec3( 0.3333333 ) ); }
highp float rand( const in vec2 uv ) {
	const highp float a = 12.9898, b = 78.233, c = 43758.5453;
	highp float dt = dot( uv.xy, vec2( a,b ) ), sn = mod( dt, PI );
	return fract( sin( sn ) * c );
}
#ifdef HIGH_PRECISION
	float precisionSafeLength( vec3 v ) { return length( v ); }
#else
	float precisionSafeLength( vec3 v ) {
		float maxComponent = max3( abs( v ) );
		return length( v / maxComponent ) * maxComponent;
	}
#endif
struct IncidentLight {
	vec3 color;
	vec3 direction;
	bool visible;
};
struct ReflectedLight {
	vec3 directDiffuse;
	vec3 directSpecular;
	vec3 indirectDiffuse;
	vec3 indirectSpecular;
};
#ifdef USE_ALPHAHASH
	varying vec3 vPosition;
#endif
vec3 transformDirection( in vec3 dir, in mat4 matrix ) {
	return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );
}
#define inverseTransformDirection transformDirectionByInverseViewMatrix
vec3 transformNormalByInverseViewMatrix( in vec3 normal, in mat4 viewMatrix ) {
	return normalize( ( vec4( normal, 0.0 ) * viewMatrix ).xyz );
}
vec3 transformDirectionByInverseViewMatrix( in vec3 dir, in mat4 viewMatrix ) {
	return normalize( ( vec4( dir, 0.0 ) * viewMatrix ).xyz );
}
bool isPerspectiveMatrix( mat4 m ) {
	return m[ 2 ][ 3 ] == - 1.0;
}
vec2 equirectUv( in vec3 dir ) {
	float u = atan( dir.z, dir.x ) * RECIPROCAL_PI2 + 0.5;
	float v = asin( clamp( dir.y, - 1.0, 1.0 ) ) * RECIPROCAL_PI + 0.5;
	return vec2( u, v );
}
vec3 BRDF_Lambert( const in vec3 diffuseColor ) {
	return RECIPROCAL_PI * diffuseColor;
}
vec3 F_Schlick( const in vec3 f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
}
float F_Schlick( const in float f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
} // validated`,mm=`#ifdef ENVMAP_TYPE_CUBE_UV
	#define cubeUV_minMipLevel 4.0
	#define cubeUV_minTileSize 16.0
	float getFace( vec3 direction ) {
		vec3 absDirection = abs( direction );
		float face = - 1.0;
		if ( absDirection.x > absDirection.z ) {
			if ( absDirection.x > absDirection.y )
				face = direction.x > 0.0 ? 0.0 : 3.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		} else {
			if ( absDirection.z > absDirection.y )
				face = direction.z > 0.0 ? 2.0 : 5.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		}
		return face;
	}
	vec2 getUV( vec3 direction, float face ) {
		vec2 uv;
		if ( face == 0.0 ) {
			uv = vec2( direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 1.0 ) {
			uv = vec2( - direction.x, - direction.z ) / abs( direction.y );
		} else if ( face == 2.0 ) {
			uv = vec2( - direction.x, direction.y ) / abs( direction.z );
		} else if ( face == 3.0 ) {
			uv = vec2( - direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 4.0 ) {
			uv = vec2( - direction.x, direction.z ) / abs( direction.y );
		} else {
			uv = vec2( direction.x, direction.y ) / abs( direction.z );
		}
		return 0.5 * ( uv + 1.0 );
	}
	vec3 bilinearCubeUV( sampler2D envMap, vec3 direction, float mipInt ) {
		float face = getFace( direction );
		float filterInt = max( cubeUV_minMipLevel - mipInt, 0.0 );
		mipInt = max( mipInt, cubeUV_minMipLevel );
		float faceSize = exp2( mipInt );
		highp vec2 uv = getUV( direction, face ) * ( faceSize - 2.0 ) + 1.0;
		if ( face > 2.0 ) {
			uv.y += faceSize;
			face -= 3.0;
		}
		uv.x += face * faceSize;
		uv.x += filterInt * 3.0 * cubeUV_minTileSize;
		uv.y += 4.0 * ( exp2( CUBEUV_MAX_MIP ) - faceSize );
		uv.x *= CUBEUV_TEXEL_WIDTH;
		uv.y *= CUBEUV_TEXEL_HEIGHT;
		#ifdef texture2DGradEXT
			return texture2DGradEXT( envMap, uv, vec2( 0.0 ), vec2( 0.0 ) ).rgb;
		#else
			return texture2D( envMap, uv ).rgb;
		#endif
	}
	#define cubeUV_r0 1.0
	#define cubeUV_m0 - 2.0
	#define cubeUV_r1 0.8
	#define cubeUV_m1 - 1.0
	#define cubeUV_r4 0.4
	#define cubeUV_m4 2.0
	#define cubeUV_r5 0.305
	#define cubeUV_m5 3.0
	#define cubeUV_r6 0.21
	#define cubeUV_m6 4.0
	float roughnessToMip( float roughness ) {
		float mip = 0.0;
		if ( roughness >= cubeUV_r1 ) {
			mip = ( cubeUV_r0 - roughness ) * ( cubeUV_m1 - cubeUV_m0 ) / ( cubeUV_r0 - cubeUV_r1 ) + cubeUV_m0;
		} else if ( roughness >= cubeUV_r4 ) {
			mip = ( cubeUV_r1 - roughness ) * ( cubeUV_m4 - cubeUV_m1 ) / ( cubeUV_r1 - cubeUV_r4 ) + cubeUV_m1;
		} else if ( roughness >= cubeUV_r5 ) {
			mip = ( cubeUV_r4 - roughness ) * ( cubeUV_m5 - cubeUV_m4 ) / ( cubeUV_r4 - cubeUV_r5 ) + cubeUV_m4;
		} else if ( roughness >= cubeUV_r6 ) {
			mip = ( cubeUV_r5 - roughness ) * ( cubeUV_m6 - cubeUV_m5 ) / ( cubeUV_r5 - cubeUV_r6 ) + cubeUV_m5;
		} else {
			mip = - 2.0 * log2( 1.16 * roughness );		}
		return mip;
	}
	vec4 textureCubeUV( sampler2D envMap, vec3 sampleDir, float roughness ) {
		float mip = clamp( roughnessToMip( roughness ), cubeUV_m0, CUBEUV_MAX_MIP );
		float mipF = fract( mip );
		float mipInt = floor( mip );
		vec3 color0 = bilinearCubeUV( envMap, sampleDir, mipInt );
		if ( mipF == 0.0 ) {
			return vec4( color0, 1.0 );
		} else {
			vec3 color1 = bilinearCubeUV( envMap, sampleDir, mipInt + 1.0 );
			return vec4( mix( color0, color1, mipF ), 1.0 );
		}
	}
#endif`,gm=`vec3 transformedNormal = objectNormal;
#ifdef USE_TANGENT
	vec3 transformedTangent = objectTangent;
#endif
#ifdef USE_BATCHING
	mat3 bm = mat3( batchingMatrix );
	transformedNormal /= vec3( dot( bm[ 0 ], bm[ 0 ] ), dot( bm[ 1 ], bm[ 1 ] ), dot( bm[ 2 ], bm[ 2 ] ) );
	transformedNormal = bm * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = bm * transformedTangent;
	#endif
#endif
#ifdef USE_INSTANCING
	mat3 im = mat3( instanceMatrix );
	transformedNormal /= vec3( dot( im[ 0 ], im[ 0 ] ), dot( im[ 1 ], im[ 1 ] ), dot( im[ 2 ], im[ 2 ] ) );
	transformedNormal = im * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = im * transformedTangent;
	#endif
#endif
transformedNormal = normalMatrix * transformedNormal;
#ifdef FLIP_SIDED
	transformedNormal = - transformedNormal;
#endif
#ifdef USE_TANGENT
	transformedTangent = ( modelViewMatrix * vec4( transformedTangent, 0.0 ) ).xyz;
#endif`,xm=`#ifdef USE_DISPLACEMENTMAP
	uniform sampler2D displacementMap;
	uniform float displacementScale;
	uniform float displacementBias;
#endif`,_m=`#ifdef USE_DISPLACEMENTMAP
	transformed += normalize( objectNormal ) * ( texture2D( displacementMap, vDisplacementMapUv ).x * displacementScale + displacementBias );
#endif`,ym=`#ifdef USE_EMISSIVEMAP
	vec4 emissiveColor = texture2D( emissiveMap, vEmissiveMapUv );
	#ifdef DECODE_VIDEO_TEXTURE_EMISSIVE
		emissiveColor = sRGBTransferEOTF( emissiveColor );
	#endif
	totalEmissiveRadiance *= emissiveColor.rgb;
#endif`,vm=`#ifdef USE_EMISSIVEMAP
	uniform sampler2D emissiveMap;
#endif`,bm="gl_FragColor = linearToOutputTexel( gl_FragColor );",Mm=`vec4 LinearTransferOETF( in vec4 value ) {
	return value;
}
vec4 sRGBTransferEOTF( in vec4 value ) {
	return vec4( mix( pow( value.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), value.rgb * 0.0773993808, vec3( lessThanEqual( value.rgb, vec3( 0.04045 ) ) ) ), value.a );
}
vec4 sRGBTransferOETF( in vec4 value ) {
	return vec4( mix( pow( value.rgb, vec3( 0.41666 ) ) * 1.055 - vec3( 0.055 ), value.rgb * 12.92, vec3( lessThanEqual( value.rgb, vec3( 0.0031308 ) ) ) ), value.a );
}`,Sm=`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vec3 cameraToFrag;
		if ( isOrthographic ) {
			cameraToFrag = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToFrag = normalize( vWorldPosition - cameraPosition );
		}
		vec3 worldNormal = transformNormalByInverseViewMatrix( normal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vec3 reflectVec = reflect( cameraToFrag, worldNormal );
		#else
			vec3 reflectVec = refract( cameraToFrag, worldNormal, refractionRatio );
		#endif
	#else
		vec3 reflectVec = vReflect;
	#endif
	#ifdef ENVMAP_TYPE_CUBE
		vec4 envColor = textureCube( envMap, envMapRotation * reflectVec );
		#ifdef ENVMAP_BLENDING_MULTIPLY
			outgoingLight = mix( outgoingLight, outgoingLight * envColor.xyz, specularStrength * reflectivity );
		#elif defined( ENVMAP_BLENDING_MIX )
			outgoingLight = mix( outgoingLight, envColor.xyz, specularStrength * reflectivity );
		#elif defined( ENVMAP_BLENDING_ADD )
			outgoingLight += envColor.xyz * specularStrength * reflectivity;
		#endif
	#endif
#endif`,Em=`#ifdef USE_ENVMAP
	uniform float envMapIntensity;
	uniform mat3 envMapRotation;
	#ifdef ENVMAP_TYPE_CUBE
		uniform samplerCube envMap;
	#else
		uniform sampler2D envMap;
	#endif
#endif`,wm=`#ifdef USE_ENVMAP
	uniform float reflectivity;
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		varying vec3 vWorldPosition;
		uniform float refractionRatio;
	#else
		varying vec3 vReflect;
	#endif
#endif`,Tm=`#ifdef USE_ENVMAP
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		
		varying vec3 vWorldPosition;
	#else
		varying vec3 vReflect;
		uniform float refractionRatio;
	#endif
#endif`,Am=`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vWorldPosition = worldPosition.xyz;
	#else
		vec3 cameraToVertex;
		if ( isOrthographic ) {
			cameraToVertex = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToVertex = normalize( worldPosition.xyz - cameraPosition );
		}
		vec3 worldNormal = transformNormalByInverseViewMatrix( transformedNormal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vReflect = reflect( cameraToVertex, worldNormal );
		#else
			vReflect = refract( cameraToVertex, worldNormal, refractionRatio );
		#endif
	#endif
#endif`,Rm=`#ifdef USE_FOG
	vFogDepth = - mvPosition.z;
#endif`,Cm=`#ifdef USE_FOG
	varying float vFogDepth;
#endif`,Pm=`#ifdef USE_FOG
	#ifdef FOG_EXP2
		float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
	#else
		float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );
	#endif
	gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );
#endif`,Im=`#ifdef USE_FOG
	uniform vec3 fogColor;
	varying float vFogDepth;
	#ifdef FOG_EXP2
		uniform float fogDensity;
	#else
		uniform float fogNear;
		uniform float fogFar;
	#endif
#endif`,Lm=`#ifdef USE_GRADIENTMAP
	uniform sampler2D gradientMap;
#endif
vec3 getGradientIrradiance( vec3 normal, vec3 lightDirection ) {
	float dotNL = dot( normal, lightDirection );
	vec2 coord = vec2( dotNL * 0.5 + 0.5, 0.0 );
	#ifdef USE_GRADIENTMAP
		return vec3( texture2D( gradientMap, coord ).r );
	#else
		vec2 fw = fwidth( coord ) * 0.5;
		return mix( vec3( 0.7 ), vec3( 1.0 ), smoothstep( 0.7 - fw.x, 0.7 + fw.x, coord.x ) );
	#endif
}`,zm=`#ifdef USE_LIGHTMAP
	uniform sampler2D lightMap;
	uniform float lightMapIntensity;
#endif`,Dm=`LambertMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularStrength = specularStrength;`,Nm=`varying vec3 vViewPosition;
struct LambertMaterial {
	vec3 diffuseColor;
	float specularStrength;
};
void RE_Direct_Lambert( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Lambert( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Lambert
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Lambert`,Um=`uniform bool receiveShadow;
uniform vec3 ambientLightColor;
#if defined( USE_LIGHT_PROBES )
	uniform vec3 lightProbe[ 9 ];
#endif
vec3 shGetIrradianceAt( in vec3 normal, in vec3 shCoefficients[ 9 ] ) {
	float x = normal.x, y = normal.y, z = normal.z;
	vec3 result = shCoefficients[ 0 ] * 0.886227;
	result += shCoefficients[ 1 ] * 2.0 * 0.511664 * y;
	result += shCoefficients[ 2 ] * 2.0 * 0.511664 * z;
	result += shCoefficients[ 3 ] * 2.0 * 0.511664 * x;
	result += shCoefficients[ 4 ] * 2.0 * 0.429043 * x * y;
	result += shCoefficients[ 5 ] * 2.0 * 0.429043 * y * z;
	result += shCoefficients[ 6 ] * ( 0.743125 * z * z - 0.247708 );
	result += shCoefficients[ 7 ] * 2.0 * 0.429043 * x * z;
	result += shCoefficients[ 8 ] * 0.429043 * ( x * x - y * y );
	return result;
}
vec3 getLightProbeIrradiance( const in vec3 lightProbe[ 9 ], const in vec3 normal ) {
	vec3 worldNormal = transformNormalByInverseViewMatrix( normal, viewMatrix );
	vec3 irradiance = shGetIrradianceAt( worldNormal, lightProbe );
	return irradiance;
}
vec3 getAmbientLightIrradiance( const in vec3 ambientLightColor ) {
	vec3 irradiance = ambientLightColor;
	return irradiance;
}
float getDistanceAttenuation( const in float lightDistance, const in float cutoffDistance, const in float decayExponent ) {
	float distanceFalloff = 1.0 / max( pow( lightDistance, decayExponent ), 0.01 );
	if ( cutoffDistance > 0.0 ) {
		distanceFalloff *= pow2( saturate( 1.0 - pow4( lightDistance / cutoffDistance ) ) );
	}
	return distanceFalloff;
}
float getSpotAttenuation( const in float coneCosine, const in float penumbraCosine, const in float angleCosine ) {
	return smoothstep( coneCosine, penumbraCosine, angleCosine );
}
#if NUM_SUN_LIGHTS > 0
	struct SunLight {
		vec3 direction;
		vec3 color;
	};
	uniform SunLight sunLights[ NUM_SUN_LIGHTS ];
	void getSunLightInfo( const in SunLight sunLight, out IncidentLight light ) {
		light.color = sunLight.color;
		light.direction = sunLight.direction;
		light.visible = true;
	}
#endif
#if NUM_DIR_LIGHTS > 0
	struct DirectionalLight {
		vec3 direction;
		vec3 color;
	};
	uniform DirectionalLight directionalLights[ NUM_DIR_LIGHTS ];
	void getDirectionalLightInfo( const in DirectionalLight directionalLight, out IncidentLight light ) {
		light.color = directionalLight.color;
		light.direction = directionalLight.direction;
		light.visible = true;
	}
#endif
#if NUM_POINT_LIGHTS > 0
	struct PointLight {
		vec3 position;
		vec3 color;
		float distance;
		float decay;
	};
	uniform PointLight pointLights[ NUM_POINT_LIGHTS ];
	void getPointLightInfo( const in PointLight pointLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = pointLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float lightDistance = length( lVector );
		light.color = pointLight.color;
		light.color *= getDistanceAttenuation( lightDistance, pointLight.distance, pointLight.decay );
		light.visible = ( light.color != vec3( 0.0 ) );
	}
#endif
#if NUM_SPOT_LIGHTS > 0
	struct SpotLight {
		vec3 position;
		vec3 direction;
		vec3 color;
		float distance;
		float decay;
		float coneCos;
		float penumbraCos;
	};
	uniform SpotLight spotLights[ NUM_SPOT_LIGHTS ];
	void getSpotLightInfo( const in SpotLight spotLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = spotLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float angleCos = dot( light.direction, spotLight.direction );
		float spotAttenuation = getSpotAttenuation( spotLight.coneCos, spotLight.penumbraCos, angleCos );
		if ( spotAttenuation > 0.0 ) {
			float lightDistance = length( lVector );
			light.color = spotLight.color * spotAttenuation;
			light.color *= getDistanceAttenuation( lightDistance, spotLight.distance, spotLight.decay );
			light.visible = ( light.color != vec3( 0.0 ) );
		} else {
			light.color = vec3( 0.0 );
			light.visible = false;
		}
	}
#endif
#if NUM_RECT_AREA_LIGHTS > 0
	struct RectAreaLight {
		vec3 color;
		vec3 position;
		vec3 halfWidth;
		vec3 halfHeight;
	};
	uniform sampler2D ltc_1;	uniform sampler2D ltc_2;
	uniform RectAreaLight rectAreaLights[ NUM_RECT_AREA_LIGHTS ];
#endif
#if NUM_HEMI_LIGHTS > 0
	struct HemisphereLight {
		vec3 direction;
		vec3 skyColor;
		vec3 groundColor;
	};
	uniform HemisphereLight hemisphereLights[ NUM_HEMI_LIGHTS ];
	vec3 getHemisphereLightIrradiance( const in HemisphereLight hemiLight, const in vec3 normal ) {
		float dotNL = dot( normal, hemiLight.direction );
		float hemiDiffuseWeight = 0.5 * dotNL + 0.5;
		vec3 irradiance = mix( hemiLight.groundColor, hemiLight.skyColor, hemiDiffuseWeight );
		return irradiance;
	}
#endif
#include <lightprobes_pars_fragment>`,Fm=`#ifdef USE_ENVMAP
	vec3 getIBLIrradiance( const in vec3 normal ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 worldNormal = transformNormalByInverseViewMatrix( normal, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * worldNormal, 1.0 );
			return PI * envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	vec3 getIBLRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 reflectVec = reflect( - viewDir, normal );
			reflectVec = normalize( mix( reflectVec, normal, pow4( roughness ) ) );
			reflectVec = transformDirectionByInverseViewMatrix( reflectVec, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * reflectVec, roughness );
			return envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	#ifdef USE_RETROREFLECTION
		vec3 getIBLRetroRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness ) {
			#ifdef ENVMAP_TYPE_CUBE_UV
				vec3 retroVec = normalize( mix( viewDir, normal, pow4( roughness ) ) );
				retroVec = transformDirectionByInverseViewMatrix( retroVec, viewMatrix );
				vec4 envMapColor = textureCubeUV( envMap, envMapRotation * retroVec, roughness );
				return envMapColor.rgb * envMapIntensity;
			#else
				return vec3( 0.0 );
			#endif
		}
	#endif
	#ifdef USE_ANISOTROPY
		vec3 getIBLAnisotropyRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness, const in vec3 bitangent, const in float anisotropy ) {
			#ifdef ENVMAP_TYPE_CUBE_UV
				vec3 bentNormal = cross( bitangent, viewDir );
				bentNormal = normalize( cross( bentNormal, bitangent ) );
				bentNormal = normalize( mix( bentNormal, normal, pow2( pow2( 1.0 - anisotropy * ( 1.0 - roughness ) ) ) ) );
				return getIBLRadiance( viewDir, bentNormal, roughness );
			#else
				return vec3( 0.0 );
			#endif
		}
		#ifdef USE_RETROREFLECTION
			vec3 getIBLAnisotropyRetroRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness, const in vec3 bitangent, const in float anisotropy ) {
				#ifdef ENVMAP_TYPE_CUBE_UV
					vec3 bentNormal = cross( bitangent, viewDir );
					bentNormal = normalize( cross( bentNormal, bitangent ) );
					bentNormal = normalize( mix( bentNormal, normal, pow2( pow2( 1.0 - anisotropy * ( 1.0 - roughness ) ) ) ) );
					return getIBLRetroRadiance( viewDir, bentNormal, roughness );
				#else
					return vec3( 0.0 );
				#endif
			}
		#endif
	#endif
#endif`,Om=`ToonMaterial material;
material.diffuseColor = diffuseColor.rgb;`,Bm=`varying vec3 vViewPosition;
struct ToonMaterial {
	vec3 diffuseColor;
};
void RE_Direct_Toon( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	vec3 irradiance = getGradientIrradiance( geometryNormal, directLight.direction ) * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Toon( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Toon
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Toon`,km=`BlinnPhongMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularColor = specular;
material.specularShininess = shininess;
material.specularStrength = specularStrength;`,Hm=`varying vec3 vViewPosition;
struct BlinnPhongMaterial {
	vec3 diffuseColor;
	vec3 specularColor;
	float specularShininess;
	float specularStrength;
};
void RE_Direct_BlinnPhong( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
	reflectedLight.directSpecular += irradiance * BRDF_BlinnPhong( directLight.direction, geometryViewDir, geometryNormal, material.specularColor, material.specularShininess ) * material.specularStrength;
}
void RE_IndirectDiffuse_BlinnPhong( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_BlinnPhong
#define RE_IndirectDiffuse		RE_IndirectDiffuse_BlinnPhong`,Vm=`PhysicalMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.diffuseContribution = diffuseColor.rgb * ( 1.0 - metalnessFactor );
material.metalness = metalnessFactor;
vec3 dxy = max( abs( dFdx( nonPerturbedNormal ) ), abs( dFdy( nonPerturbedNormal ) ) );
float geometryRoughness = max( max( dxy.x, dxy.y ), dxy.z );
material.roughness = max( roughnessFactor, 0.0525 );material.roughness += geometryRoughness;
material.roughness = min( material.roughness, 1.0 );
#ifdef IOR
	material.ior = ior;
	#ifdef USE_SPECULAR
		float specularIntensityFactor = specularIntensity;
		vec3 specularColorFactor = specularColor;
		#ifdef USE_SPECULAR_COLORMAP
			specularColorFactor *= texture2D( specularColorMap, vSpecularColorMapUv ).rgb;
		#endif
		#ifdef USE_SPECULAR_INTENSITYMAP
			specularIntensityFactor *= texture2D( specularIntensityMap, vSpecularIntensityMapUv ).a;
		#endif
		material.specularF90 = mix( specularIntensityFactor, 1.0, metalnessFactor );
	#else
		float specularIntensityFactor = 1.0;
		vec3 specularColorFactor = vec3( 1.0 );
		material.specularF90 = 1.0;
	#endif
	material.specularColor = min( pow2( ( material.ior - 1.0 ) / ( material.ior + 1.0 ) ) * specularColorFactor, vec3( 1.0 ) ) * specularIntensityFactor;
	material.specularColorBlended = mix( material.specularColor, diffuseColor.rgb, metalnessFactor );
#else
	material.specularColor = vec3( 0.04 );
	material.specularColorBlended = mix( material.specularColor, diffuseColor.rgb, metalnessFactor );
	material.specularF90 = 1.0;
#endif
#ifdef USE_CLEARCOAT
	material.clearcoat = clearcoat;
	material.clearcoatRoughness = clearcoatRoughness;
	material.clearcoatF0 = vec3( 0.04 );
	material.clearcoatF90 = 1.0;
	#ifdef USE_CLEARCOATMAP
		material.clearcoat *= texture2D( clearcoatMap, vClearcoatMapUv ).x;
	#endif
	#ifdef USE_CLEARCOAT_ROUGHNESSMAP
		material.clearcoatRoughness *= texture2D( clearcoatRoughnessMap, vClearcoatRoughnessMapUv ).y;
	#endif
	material.clearcoat = saturate( material.clearcoat );	material.clearcoatRoughness = max( material.clearcoatRoughness, 0.0525 );
	material.clearcoatRoughness += geometryRoughness;
	material.clearcoatRoughness = min( material.clearcoatRoughness, 1.0 );
#endif
#ifdef USE_DISPERSION
	material.dispersion = dispersion;
#endif
#ifdef USE_RETROREFLECTION
	material.retroreflectivity = retroreflectivity;
#endif
#ifdef USE_IRIDESCENCE
	material.iridescence = iridescence;
	material.iridescenceIOR = iridescenceIOR;
	#ifdef USE_IRIDESCENCEMAP
		material.iridescence *= texture2D( iridescenceMap, vIridescenceMapUv ).r;
	#endif
	#ifdef USE_IRIDESCENCE_THICKNESSMAP
		material.iridescenceThickness = (iridescenceThicknessMaximum - iridescenceThicknessMinimum) * texture2D( iridescenceThicknessMap, vIridescenceThicknessMapUv ).g + iridescenceThicknessMinimum;
	#else
		material.iridescenceThickness = iridescenceThicknessMaximum;
	#endif
#endif
#ifdef USE_SHEEN
	material.sheenColor = sheenColor;
	#ifdef USE_SHEEN_COLORMAP
		material.sheenColor *= texture2D( sheenColorMap, vSheenColorMapUv ).rgb;
	#endif
	material.sheenRoughness = clamp( sheenRoughness, 0.0001, 1.0 );
	#ifdef USE_SHEEN_ROUGHNESSMAP
		material.sheenRoughness *= texture2D( sheenRoughnessMap, vSheenRoughnessMapUv ).a;
	#endif
#endif
#ifdef USE_ANISOTROPY
	#ifdef USE_ANISOTROPYMAP
		mat2 anisotropyMat = mat2( anisotropyVector.x, anisotropyVector.y, - anisotropyVector.y, anisotropyVector.x );
		vec3 anisotropyPolar = texture2D( anisotropyMap, vAnisotropyMapUv ).rgb;
		vec2 anisotropyV = anisotropyMat * normalize( 2.0 * anisotropyPolar.rg - vec2( 1.0 ) ) * anisotropyPolar.b;
	#else
		vec2 anisotropyV = anisotropyVector;
	#endif
	material.anisotropy = length( anisotropyV );
	if( material.anisotropy == 0.0 ) {
		anisotropyV = vec2( 1.0, 0.0 );
	} else {
		anisotropyV /= material.anisotropy;
		material.anisotropy = saturate( material.anisotropy );
	}
	material.alphaT = mix( pow2( material.roughness ), 1.0, pow2( material.anisotropy ) );
	material.anisotropyT = tbn[ 0 ] * anisotropyV.x + tbn[ 1 ] * anisotropyV.y;
	material.anisotropyB = tbn[ 1 ] * anisotropyV.x - tbn[ 0 ] * anisotropyV.y;
#endif`,Gm=`uniform sampler2D dfgLUT;
struct PhysicalMaterial {
	vec3 diffuseColor;
	vec3 diffuseContribution;
	vec3 specularColor;
	vec3 specularColorBlended;
	float roughness;
	float metalness;
	float specularF90;
	float dispersion;
	vec2 dfg;
	vec3 multiScatteringCompensation;
	#ifdef USE_RETROREFLECTION
		float retroreflectivity;
	#endif
	#ifdef USE_CLEARCOAT
		float clearcoat;
		float clearcoatRoughness;
		vec3 clearcoatF0;
		float clearcoatF90;
	#endif
	#ifdef USE_IRIDESCENCE
		float iridescence;
		float iridescenceIOR;
		float iridescenceThickness;
		vec3 iridescenceFresnel;
		vec3 iridescenceF0Dielectric;
		vec3 iridescenceF0Metallic;
	#endif
	#ifdef USE_SHEEN
		vec3 sheenColor;
		float sheenRoughness;
	#endif
	#ifdef IOR
		float ior;
	#endif
	#ifdef USE_TRANSMISSION
		float transmission;
		float transmissionAlpha;
		float thickness;
		float attenuationDistance;
		vec3 attenuationColor;
	#endif
	#ifdef USE_ANISOTROPY
		float anisotropy;
		float alphaT;
		vec3 anisotropyT;
		vec3 anisotropyB;
	#endif
};
vec3 clearcoatSpecularDirect = vec3( 0.0 );
vec3 clearcoatSpecularIndirect = vec3( 0.0 );
vec3 sheenSpecularDirect = vec3( 0.0 );
vec3 sheenSpecularIndirect = vec3(0.0 );
vec3 Schlick_to_F0( const in vec3 f, const in float f90, const in float dotVH ) {
    float x = clamp( 1.0 - dotVH, 0.0, 1.0 );
    float x2 = x * x;
    float x5 = clamp( x * x2 * x2, 0.0, 0.9999 );
    return ( f - vec3( f90 ) * x5 ) / ( 1.0 - x5 );
}
float V_GGX_SmithCorrelated( const in float alpha, const in float dotNL, const in float dotNV ) {
	float a2 = pow2( alpha );
	float gv = dotNL * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNV ) );
	float gl = dotNV * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNL ) );
	return 0.5 / max( gv + gl, EPSILON );
}
float D_GGX( const in float alpha, const in float dotNH ) {
	float a2 = pow2( alpha );
	float denom = pow2( dotNH ) * ( a2 - 1.0 ) + 1.0;
	return RECIPROCAL_PI * a2 / pow2( denom );
}
#ifdef USE_ANISOTROPY
	float V_GGX_SmithCorrelated_Anisotropic( const in float alphaT, const in float alphaB, const in float dotTV, const in float dotBV, const in float dotTL, const in float dotBL, const in float dotNV, const in float dotNL ) {
		float gv = dotNL * length( vec3( alphaT * dotTV, alphaB * dotBV, dotNV ) );
		float gl = dotNV * length( vec3( alphaT * dotTL, alphaB * dotBL, dotNL ) );
		return 0.5 / max( gv + gl, EPSILON );
	}
	float D_GGX_Anisotropic( const in float alphaT, const in float alphaB, const in float dotNH, const in float dotTH, const in float dotBH ) {
		float a2 = alphaT * alphaB;
		highp vec3 v = vec3( alphaB * dotTH, alphaT * dotBH, a2 * dotNH );
		highp float v2 = dot( v, v );
		float w2 = a2 / v2;
		return RECIPROCAL_PI * a2 * pow2 ( w2 );
	}
#endif
#ifdef USE_CLEARCOAT
	vec3 BRDF_GGX_Clearcoat( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material) {
		vec3 f0 = material.clearcoatF0;
		float f90 = material.clearcoatF90;
		float roughness = material.clearcoatRoughness;
		float alpha = pow2( roughness );
		vec3 halfDir = normalize( lightDir + viewDir );
		float dotNL = saturate( dot( normal, lightDir ) );
		float dotNV = saturate( dot( normal, viewDir ) );
		float dotNH = saturate( dot( normal, halfDir ) );
		float dotVH = saturate( dot( viewDir, halfDir ) );
		vec3 F = F_Schlick( f0, f90, dotVH );
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
		return F * ( V * D );
	}
#endif
vec3 BRDF_GGX( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material ) {
	vec3 f0 = material.specularColorBlended;
	float f90 = material.specularF90;
	float roughness = material.roughness;
	float alpha = pow2( roughness );
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( f0, f90, dotVH );
	#ifdef USE_IRIDESCENCE
		F = mix( F, material.iridescenceFresnel, material.iridescence );
	#endif
	#ifdef USE_ANISOTROPY
		float dotTL = dot( material.anisotropyT, lightDir );
		float dotTV = dot( material.anisotropyT, viewDir );
		float dotTH = dot( material.anisotropyT, halfDir );
		float dotBL = dot( material.anisotropyB, lightDir );
		float dotBV = dot( material.anisotropyB, viewDir );
		float dotBH = dot( material.anisotropyB, halfDir );
		float V = V_GGX_SmithCorrelated_Anisotropic( material.alphaT, alpha, dotTV, dotBV, dotTL, dotBL, dotNV, dotNL );
		float D = D_GGX_Anisotropic( material.alphaT, alpha, dotNH, dotTH, dotBH );
	#else
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
	#endif
	return F * ( V * D );
}
vec2 LTC_Uv( const in vec3 N, const in vec3 V, const in float roughness ) {
	const float LUT_SIZE = 64.0;
	const float LUT_SCALE = ( LUT_SIZE - 1.0 ) / LUT_SIZE;
	const float LUT_BIAS = 0.5 / LUT_SIZE;
	float dotNV = saturate( dot( N, V ) );
	vec2 uv = vec2( roughness, sqrt( 1.0 - dotNV ) );
	uv = uv * LUT_SCALE + LUT_BIAS;
	return uv;
}
float LTC_ClippedSphereFormFactor( const in vec3 f ) {
	float l = length( f );
	return max( ( l * l + f.z ) / ( l + 1.0 ), 0.0 );
}
vec3 LTC_EdgeVectorFormFactor( const in vec3 v1, const in vec3 v2 ) {
	float x = dot( v1, v2 );
	float y = abs( x );
	float a = 0.8543985 + ( 0.4965155 + 0.0145206 * y ) * y;
	float b = 3.4175940 + ( 4.1616724 + y ) * y;
	float v = a / b;
	float theta_sintheta = ( x > 0.0 ) ? v : 0.5 * inversesqrt( max( 1.0 - x * x, 1e-7 ) ) - v;
	return cross( v1, v2 ) * theta_sintheta;
}
vec3 LTC_Evaluate( const in vec3 N, const in vec3 V, const in vec3 P, const in mat3 mInv, const in vec3 rectCoords[ 4 ] ) {
	vec3 v1 = rectCoords[ 1 ] - rectCoords[ 0 ];
	vec3 v2 = rectCoords[ 3 ] - rectCoords[ 0 ];
	vec3 lightNormal = cross( v1, v2 );
	if( dot( lightNormal, P - rectCoords[ 0 ] ) < 0.0 ) return vec3( 0.0 );
	vec3 T1, T2;
	T1 = normalize( V - N * dot( V, N ) );
	T2 = - cross( N, T1 );
	mat3 mat = mInv * transpose( mat3( T1, T2, N ) );
	vec3 coords[ 4 ];
	coords[ 0 ] = mat * ( rectCoords[ 0 ] - P );
	coords[ 1 ] = mat * ( rectCoords[ 1 ] - P );
	coords[ 2 ] = mat * ( rectCoords[ 2 ] - P );
	coords[ 3 ] = mat * ( rectCoords[ 3 ] - P );
	coords[ 0 ] = normalize( coords[ 0 ] );
	coords[ 1 ] = normalize( coords[ 1 ] );
	coords[ 2 ] = normalize( coords[ 2 ] );
	coords[ 3 ] = normalize( coords[ 3 ] );
	vec3 vectorFormFactor = vec3( 0.0 );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 0 ], coords[ 1 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 1 ], coords[ 2 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 2 ], coords[ 3 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 3 ], coords[ 0 ] );
	float result = LTC_ClippedSphereFormFactor( vectorFormFactor );
	return vec3( result );
}
#if defined( USE_SHEEN )
float D_Charlie( float roughness, float dotNH ) {
	float alpha = pow2( roughness );
	float invAlpha = 1.0 / alpha;
	float cos2h = dotNH * dotNH;
	float sin2h = max( 1.0 - cos2h, 0.0078125 );
	return ( 2.0 + invAlpha ) * pow( sin2h, invAlpha * 0.5 ) / ( 2.0 * PI );
}
float V_Neubelt( float dotNV, float dotNL ) {
	return saturate( 1.0 / ( 4.0 * ( dotNL + dotNV - dotNL * dotNV ) ) );
}
vec3 BRDF_Sheen( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, vec3 sheenColor, const in float sheenRoughness ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float D = D_Charlie( sheenRoughness, dotNH );
	float V = V_Neubelt( dotNV, dotNL );
	return sheenColor * ( D * V );
}
#endif
float IBLSheenBRDF( const in vec3 normal, const in vec3 viewDir, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	float r2 = roughness * roughness;
	float rInv = 1.0 / ( roughness + 0.1 );
	float a = -1.9362 + 1.0678 * roughness + 0.4573 * r2 - 0.8469 * rInv;
	float b = -0.6014 + 0.5538 * roughness - 0.4670 * r2 - 0.1255 * rInv;
	float DG = exp( a * dotNV + b );
	return saturate( DG );
}
vec3 EnvironmentBRDF( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	vec2 fab = texture2D( dfgLUT, vec2( roughness, dotNV ) ).rg;
	return specularColor * fab.x + specularF90 * fab.y;
}
#ifdef USE_IRIDESCENCE
void computeMultiscatteringIridescence( const in vec2 fab, const in vec3 specularColor, const in float specularF90, const in float iridescence, const in vec3 iridescenceF0, inout vec3 singleScatter, inout vec3 multiScatter ) {
#else
void computeMultiscattering( const in vec2 fab, const in vec3 specularColor, const in float specularF90, inout vec3 singleScatter, inout vec3 multiScatter ) {
#endif
	#ifdef USE_IRIDESCENCE
		vec3 Fr = mix( specularColor, iridescenceF0, iridescence );
	#else
		vec3 Fr = specularColor;
	#endif
	vec3 FssEss = Fr * fab.x + specularF90 * fab.y;
	float Ess = fab.x + fab.y;
	float Ems = 1.0 - Ess;
	vec3 Favg = Fr + ( 1.0 - Fr ) * 0.047619;	vec3 Fms = FssEss * Favg / ( 1.0 - Ems * Favg );
	singleScatter += FssEss;
	multiScatter += Fms * Ems;
}
#if NUM_RECT_AREA_LIGHTS > 0
	void RE_Direct_RectArea_Physical( const in RectAreaLight rectAreaLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
		vec3 normal = geometryNormal;
		vec3 viewDir = geometryViewDir;
		vec3 position = geometryPosition;
		vec3 lightPos = rectAreaLight.position;
		vec3 halfWidth = rectAreaLight.halfWidth;
		vec3 halfHeight = rectAreaLight.halfHeight;
		vec3 lightColor = rectAreaLight.color;
		float roughness = material.roughness;
		vec3 rectCoords[ 4 ];
		rectCoords[ 0 ] = lightPos + halfWidth - halfHeight;		rectCoords[ 1 ] = lightPos - halfWidth - halfHeight;
		rectCoords[ 2 ] = lightPos - halfWidth + halfHeight;
		rectCoords[ 3 ] = lightPos + halfWidth + halfHeight;
		vec2 uv = LTC_Uv( normal, viewDir, roughness );
		vec4 t1 = texture2D( ltc_1, uv );
		vec4 t2 = texture2D( ltc_2, uv );
		mat3 mInv = mat3(
			vec3( t1.x, 0, t1.y ),
			vec3(    0, 1,    0 ),
			vec3( t1.z, 0, t1.w )
		);
		vec3 fresnel = ( material.specularColorBlended * t2.x + ( material.specularF90 - material.specularColorBlended ) * t2.y );
		reflectedLight.directSpecular += lightColor * fresnel * LTC_Evaluate( normal, viewDir, position, mInv, rectCoords );
		reflectedLight.directDiffuse += lightColor * material.diffuseContribution * LTC_Evaluate( normal, viewDir, position, mat3( 1.0 ), rectCoords );
		#ifdef USE_CLEARCOAT
			vec3 Ncc = geometryClearcoatNormal;
			vec2 uvClearcoat = LTC_Uv( Ncc, viewDir, material.clearcoatRoughness );
			vec4 t1Clearcoat = texture2D( ltc_1, uvClearcoat );
			vec4 t2Clearcoat = texture2D( ltc_2, uvClearcoat );
			mat3 mInvClearcoat = mat3(
				vec3( t1Clearcoat.x, 0, t1Clearcoat.y ),
				vec3(             0, 1,             0 ),
				vec3( t1Clearcoat.z, 0, t1Clearcoat.w )
			);
			vec3 fresnelClearcoat = material.clearcoatF0 * t2Clearcoat.x + ( material.clearcoatF90 - material.clearcoatF0 ) * t2Clearcoat.y;
			clearcoatSpecularDirect += lightColor * fresnelClearcoat * LTC_Evaluate( Ncc, viewDir, position, mInvClearcoat, rectCoords );
		#endif
	}
#endif
void RE_Direct_Physical( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	#ifdef USE_CLEARCOAT
		float dotNLcc = saturate( dot( geometryClearcoatNormal, directLight.direction ) );
		vec3 ccIrradiance = dotNLcc * directLight.color;
		clearcoatSpecularDirect += ccIrradiance * BRDF_GGX_Clearcoat( directLight.direction, geometryViewDir, geometryClearcoatNormal, material );
	#endif
	#ifdef USE_SHEEN
 
 		sheenSpecularDirect += irradiance * BRDF_Sheen( directLight.direction, geometryViewDir, geometryNormal, material.sheenColor, material.sheenRoughness );
 
 		float sheenAlbedoV = IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness );
 		float sheenAlbedoL = IBLSheenBRDF( geometryNormal, directLight.direction, material.sheenRoughness );
 
 		float sheenEnergyComp = 1.0 - max3( material.sheenColor ) * max( sheenAlbedoV, sheenAlbedoL );
 
 		irradiance *= sheenEnergyComp;
 
 	#endif
	vec3 specularBRDF = BRDF_GGX( directLight.direction, geometryViewDir, geometryNormal, material );
	#ifdef USE_RETROREFLECTION
		vec3 retroViewDir = reflect( - geometryViewDir, geometryNormal );
		vec3 retroSpecularBRDF = BRDF_GGX( directLight.direction, retroViewDir, geometryNormal, material );
		specularBRDF = mix( specularBRDF, retroSpecularBRDF, saturate( material.retroreflectivity ) );
	#endif
	reflectedLight.directSpecular += irradiance * specularBRDF * material.multiScatteringCompensation;
	vec3 halfDir = normalize( directLight.direction + geometryViewDir );
	float dotVH = saturate( dot( geometryViewDir, halfDir ) );
	vec3 F = F_Schlick( material.specularColor, material.specularF90, dotVH );
	#ifdef USE_RETROREFLECTION
		vec3 retroHalfDir = normalize( directLight.direction + retroViewDir );
		float dotRetroVH = saturate( dot( retroViewDir, retroHalfDir ) );
		vec3 retroF = F_Schlick( material.specularColor, material.specularF90, dotRetroVH );
		F = mix( F, retroF, saturate( material.retroreflectivity ) );
	#endif
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseContribution ) * ( 1.0 - F );
}
void RE_IndirectDiffuse_Physical( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	vec3 singleScattering = vec3( 0.0 );
	vec3 multiScattering = vec3( 0.0 );
	#ifdef USE_IRIDESCENCE
		computeMultiscatteringIridescence( material.dfg, material.specularColor, material.specularF90, material.iridescence, material.iridescenceF0Dielectric, singleScattering, multiScattering );
	#else
		computeMultiscattering( material.dfg, material.specularColor, material.specularF90, singleScattering, multiScattering );
	#endif
	vec3 diffuse = irradiance * BRDF_Lambert( material.diffuseContribution ) * ( 1.0 - singleScattering - multiScattering );
	#ifdef USE_SHEEN
		float sheenAlbedo = IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness );
		sheenSpecularIndirect += irradiance * material.sheenColor * sheenAlbedo * RECIPROCAL_PI;
		float sheenEnergyComp = 1.0 - max3( material.sheenColor ) * sheenAlbedo;
		diffuse *= sheenEnergyComp;
	#endif
	reflectedLight.indirectDiffuse += diffuse;
}
void RE_IndirectSpecular_Physical( const in vec3 radiance, const in vec3 irradiance, const in vec3 clearcoatRadiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight) {
	#ifdef USE_CLEARCOAT
		clearcoatSpecularIndirect += clearcoatRadiance * EnvironmentBRDF( geometryClearcoatNormal, geometryViewDir, material.clearcoatF0, material.clearcoatF90, material.clearcoatRoughness );
	#endif
	#ifdef USE_SHEEN
		sheenSpecularIndirect += irradiance * material.sheenColor * IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness ) * RECIPROCAL_PI;
 	#endif
	vec3 singleScatteringDielectric = vec3( 0.0 );
	vec3 multiScatteringDielectric = vec3( 0.0 );
	vec3 singleScatteringMetallic = vec3( 0.0 );
	vec3 multiScatteringMetallic = vec3( 0.0 );
	#ifdef USE_IRIDESCENCE
		computeMultiscatteringIridescence( material.dfg, material.specularColor, material.specularF90, material.iridescence, material.iridescenceF0Dielectric, singleScatteringDielectric, multiScatteringDielectric );
		computeMultiscatteringIridescence( material.dfg, material.diffuseColor, material.specularF90, material.iridescence, material.iridescenceF0Metallic, singleScatteringMetallic, multiScatteringMetallic );
	#else
		computeMultiscattering( material.dfg, material.specularColor, material.specularF90, singleScatteringDielectric, multiScatteringDielectric );
		computeMultiscattering( material.dfg, material.diffuseColor, material.specularF90, singleScatteringMetallic, multiScatteringMetallic );
	#endif
	vec3 singleScattering = mix( singleScatteringDielectric, singleScatteringMetallic, material.metalness );
	vec3 multiScattering = mix( multiScatteringDielectric, multiScatteringMetallic, material.metalness );
	vec3 totalScatteringDielectric = singleScatteringDielectric + multiScatteringDielectric;
	vec3 diffuse = material.diffuseContribution * ( 1.0 - totalScatteringDielectric );
	vec3 cosineWeightedIrradiance = irradiance * RECIPROCAL_PI;
	vec3 indirectSpecular = radiance * singleScattering;
	indirectSpecular += multiScattering * cosineWeightedIrradiance;
	vec3 indirectDiffuse = diffuse * cosineWeightedIrradiance;
	#ifdef USE_SHEEN
		float sheenAlbedo = IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness );
		float sheenEnergyComp = 1.0 - max3( material.sheenColor ) * sheenAlbedo;
		indirectSpecular *= sheenEnergyComp;
		indirectDiffuse *= sheenEnergyComp;
	#endif
	reflectedLight.indirectSpecular += indirectSpecular;
	reflectedLight.indirectDiffuse += indirectDiffuse;
}
#define RE_Direct				RE_Direct_Physical
#define RE_Direct_RectArea		RE_Direct_RectArea_Physical
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Physical
#define RE_IndirectSpecular		RE_IndirectSpecular_Physical
float computeSpecularOcclusion( const in float dotNV, const in float ambientOcclusion, const in float roughness ) {
	return saturate( pow( dotNV + ambientOcclusion, exp2( - 16.0 * roughness - 1.0 ) ) - 1.0 + ambientOcclusion );
}`,Wm=`
vec3 geometryPosition = - vViewPosition;
vec3 geometryNormal = normal;
vec3 geometryViewDir = ( isOrthographic ) ? vec3( 0, 0, 1 ) : normalize( vViewPosition );
vec3 geometryClearcoatNormal = vec3( 0.0 );
#ifdef USE_CLEARCOAT
	geometryClearcoatNormal = clearcoatNormal;
#endif
#ifdef USE_IRIDESCENCE
	float dotNVi = saturate( dot( normal, geometryViewDir ) );
	if ( material.iridescenceThickness == 0.0 ) {
		material.iridescence = 0.0;
	} else {
		material.iridescence = saturate( material.iridescence );
	}
	if ( material.iridescence > 0.0 ) {
		vec3 iridescenceFresnelDielectric = evalIridescence( 1.0, material.iridescenceIOR, dotNVi, material.iridescenceThickness, material.specularColor );
		vec3 iridescenceFresnelMetallic = evalIridescence( 1.0, material.iridescenceIOR, dotNVi, material.iridescenceThickness, material.diffuseColor );
		material.iridescenceFresnel = mix( iridescenceFresnelDielectric, iridescenceFresnelMetallic, material.metalness );
		material.iridescenceF0Dielectric = Schlick_to_F0( iridescenceFresnelDielectric, 1.0, dotNVi );
		material.iridescenceF0Metallic = Schlick_to_F0( iridescenceFresnelMetallic, 1.0, dotNVi );
	}
#endif
#ifdef STANDARD
	float dotNVms = saturate( dot( geometryNormal, geometryViewDir ) );
	material.dfg = texture2D( dfgLUT, vec2( material.roughness, dotNVms ) ).rg;
	#if ( NUM_SUN_LIGHTS > 0 || NUM_DIR_LIGHTS > 0 || NUM_POINT_LIGHTS > 0 || NUM_SPOT_LIGHTS > 0 )
		float EssMs = material.dfg.x + material.dfg.y;
		material.multiScatteringCompensation = 1.0 + material.specularColorBlended * ( 1.0 / EssMs - 1.0 );
	#endif
#endif
IncidentLight directLight;
#if ( NUM_POINT_LIGHTS > 0 ) && defined( RE_Direct )
	PointLight pointLight;
	#if defined( USE_SHADOWMAP ) && NUM_POINT_LIGHT_SHADOWS > 0
	PointLightShadow pointLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHTS; i ++ ) {
		pointLight = pointLights[ i ];
		getPointLightInfo( pointLight, geometryPosition, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_POINT_LIGHT_SHADOWS ) && ( defined( SHADOWMAP_TYPE_PCF ) || defined( SHADOWMAP_TYPE_BASIC ) )
		pointLightShadow = pointLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getPointShadow( pointShadowMap[ i ], pointLightShadow.shadowMapSize, pointLightShadow.shadowIntensity, pointLightShadow.shadowBias, pointLightShadow.shadowRadius, vPointShadowCoord[ i ], pointLightShadow.shadowCameraNear, pointLightShadow.shadowCameraFar ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_SPOT_LIGHTS > 0 ) && defined( RE_Direct )
	SpotLight spotLight;
	vec4 spotColor;
	vec3 spotLightCoord;
	bool inSpotLightMap;
	#if defined( USE_SHADOWMAP ) && NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHTS; i ++ ) {
		spotLight = spotLights[ i ];
		getSpotLightInfo( spotLight, geometryPosition, directLight );
		#if ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#define SPOT_LIGHT_MAP_INDEX UNROLLED_LOOP_INDEX
		#elif ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		#define SPOT_LIGHT_MAP_INDEX NUM_SPOT_LIGHT_MAPS
		#else
		#define SPOT_LIGHT_MAP_INDEX ( UNROLLED_LOOP_INDEX - NUM_SPOT_LIGHT_SHADOWS + NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#endif
		#if ( SPOT_LIGHT_MAP_INDEX < NUM_SPOT_LIGHT_MAPS )
			spotLightCoord = vSpotLightCoord[ i ].xyz / vSpotLightCoord[ i ].w;
			inSpotLightMap = all( lessThan( abs( spotLightCoord * 2. - 1. ), vec3( 1.0 ) ) );
			spotColor = texture2D( spotLightMap[ SPOT_LIGHT_MAP_INDEX ], spotLightCoord.xy );
			directLight.color = inSpotLightMap ? directLight.color * spotColor.rgb : directLight.color;
		#endif
		#undef SPOT_LIGHT_MAP_INDEX
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		spotLightShadow = spotLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowIntensity, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_SUN_LIGHTS > 0 ) && defined( RE_Direct )
	SunLight sunLight;
	#if defined( USE_SHADOWMAP ) && NUM_SUN_LIGHT_SHADOWS > 0
	SunLightShadow sunLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SUN_LIGHTS; i ++ ) {
		sunLight = sunLights[ i ];
		getSunLightInfo( sunLight, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SUN_LIGHT_SHADOWS )
		sunLightShadow = sunLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getSunShadow( sunShadowMap[ i ], sunLightShadow, UNROLLED_LOOP_INDEX ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_DIR_LIGHTS > 0 ) && defined( RE_Direct )
	DirectionalLight directionalLight;
	#if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHTS; i ++ ) {
		directionalLight = directionalLights[ i ];
		getDirectionalLightInfo( directionalLight, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_DIR_LIGHT_SHADOWS )
		directionalLightShadow = directionalLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_RECT_AREA_LIGHTS > 0 ) && defined( RE_Direct_RectArea )
	RectAreaLight rectAreaLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_RECT_AREA_LIGHTS; i ++ ) {
		rectAreaLight = rectAreaLights[ i ];
		RE_Direct_RectArea( rectAreaLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if defined( RE_IndirectDiffuse )
	vec3 iblIrradiance = vec3( 0.0 );
	vec3 irradiance = getAmbientLightIrradiance( ambientLightColor );
	#if defined( USE_LIGHT_PROBES )
		irradiance += getLightProbeIrradiance( lightProbe, geometryNormal );
	#endif
	#if ( NUM_HEMI_LIGHTS > 0 )
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_HEMI_LIGHTS; i ++ ) {
			irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal );
		}
		#pragma unroll_loop_end
	#endif
	#ifdef USE_LIGHT_PROBES_GRID
		vec3 probeWorldPos = ( ( vec4( geometryPosition, 1.0 ) - viewMatrix[ 3 ] ) * viewMatrix ).xyz;
		vec3 probeWorldNormal = transformNormalByInverseViewMatrix( geometryNormal, viewMatrix );
		irradiance += getLightProbeGridIrradiance( probeWorldPos, probeWorldNormal );
	#endif
#endif
#if defined( RE_IndirectSpecular )
	vec3 radiance = vec3( 0.0 );
	vec3 clearcoatRadiance = vec3( 0.0 );
#endif`,Xm=`#if defined( RE_IndirectDiffuse )
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		vec3 lightMapIrradiance = lightMapTexel.rgb * lightMapIntensity;
		irradiance += lightMapIrradiance;
	#endif
	#if defined( USE_ENVMAP ) && defined( ENVMAP_TYPE_CUBE_UV )
		#if defined( STANDARD ) || defined( LAMBERT ) || defined( PHONG )
			iblIrradiance += getIBLIrradiance( geometryNormal );
		#endif
	#endif
#endif
#if defined( USE_ENVMAP ) && defined( RE_IndirectSpecular )
	#ifdef USE_ANISOTROPY
		vec3 iblRadiance = getIBLAnisotropyRadiance( geometryViewDir, geometryNormal, material.roughness, material.anisotropyB, material.anisotropy );
	#else
		vec3 iblRadiance = getIBLRadiance( geometryViewDir, geometryNormal, material.roughness );
	#endif
	#ifdef USE_RETROREFLECTION
		#ifdef USE_ANISOTROPY
			vec3 retroIBLRadiance = getIBLAnisotropyRetroRadiance( geometryViewDir, geometryNormal, material.roughness, material.anisotropyB, material.anisotropy );
		#else
			vec3 retroIBLRadiance = getIBLRetroRadiance( geometryViewDir, geometryNormal, material.roughness );
		#endif
		iblRadiance = mix( iblRadiance, retroIBLRadiance, saturate( material.retroreflectivity ) );
	#endif
	radiance += iblRadiance;
	#ifdef USE_CLEARCOAT
		clearcoatRadiance += getIBLRadiance( geometryViewDir, geometryClearcoatNormal, material.clearcoatRoughness );
	#endif
#endif`,qm=`#if defined( RE_IndirectDiffuse )
	#if defined( LAMBERT ) || defined( PHONG )
		irradiance += iblIrradiance;
	#endif
	RE_IndirectDiffuse( irradiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif
#if defined( RE_IndirectSpecular )
	RE_IndirectSpecular( radiance, iblIrradiance, clearcoatRadiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif`,Ym=`#ifdef USE_LIGHT_PROBES_GRID
uniform highp sampler3D probesSH;
uniform vec3 probesMin;
uniform vec3 probesMax;
uniform vec3 probesResolution;
vec3 getLightProbeGridIrradiance( vec3 worldPos, vec3 worldNormal ) {
	vec3 res = probesResolution;
	vec3 gridRange = probesMax - probesMin;
	vec3 resMinusOne = res - 1.0;
	vec3 probeSpacing = gridRange / resMinusOne;
	vec3 samplePos = worldPos + worldNormal * probeSpacing * 0.5;
	vec3 uvw = clamp( ( samplePos - probesMin ) / gridRange, 0.0, 1.0 );
	uvw = uvw * resMinusOne / res + 0.5 / res;
	float nz          = res.z;
	float paddedSlices = nz + 2.0;
	float atlasDepth  = 7.0 * paddedSlices;
	float uvZBase     = uvw.z * nz + 1.0;
	vec4 s0 = texture( probesSH, vec3( uvw.xy, ( uvZBase                       ) / atlasDepth ) );
	vec4 s1 = texture( probesSH, vec3( uvw.xy, ( uvZBase +       paddedSlices   ) / atlasDepth ) );
	vec4 s2 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 2.0 * paddedSlices   ) / atlasDepth ) );
	vec4 s3 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 3.0 * paddedSlices   ) / atlasDepth ) );
	vec4 s4 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 4.0 * paddedSlices   ) / atlasDepth ) );
	vec4 s5 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 5.0 * paddedSlices   ) / atlasDepth ) );
	vec4 s6 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 6.0 * paddedSlices   ) / atlasDepth ) );
	vec3 c0 = s0.xyz;
	vec3 c1 = vec3( s0.w, s1.xy );
	vec3 c2 = vec3( s1.zw, s2.x );
	vec3 c3 = s2.yzw;
	vec3 c4 = s3.xyz;
	vec3 c5 = vec3( s3.w, s4.xy );
	vec3 c6 = vec3( s4.zw, s5.x );
	vec3 c7 = s5.yzw;
	vec3 c8 = s6.xyz;
	float x = worldNormal.x, y = worldNormal.y, z = worldNormal.z;
	vec3 result = c0 * 0.886227;
	result += c1 * 2.0 * 0.511664 * y;
	result += c2 * 2.0 * 0.511664 * z;
	result += c3 * 2.0 * 0.511664 * x;
	result += c4 * 2.0 * 0.429043 * x * y;
	result += c5 * 2.0 * 0.429043 * y * z;
	result += c6 * ( 0.743125 * z * z - 0.247708 );
	result += c7 * 2.0 * 0.429043 * x * z;
	result += c8 * 0.429043 * ( x * x - y * y );
	return max( result, vec3( 0.0 ) );
}
#endif`,Zm=`#if defined( USE_LOGARITHMIC_DEPTH_BUFFER )
	gl_FragDepth = vIsPerspective == 0.0 ? gl_FragCoord.z : log2( vFragDepth ) * logDepthBufFC * 0.5;
#endif`,$m=`#if defined( USE_LOGARITHMIC_DEPTH_BUFFER )
	uniform float logDepthBufFC;
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,Km=`#ifdef USE_LOGARITHMIC_DEPTH_BUFFER
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,Jm=`#ifdef USE_LOGARITHMIC_DEPTH_BUFFER
	vFragDepth = 1.0 + gl_Position.w;
	vIsPerspective = float( isPerspectiveMatrix( projectionMatrix ) );
#endif`,jm=`#ifdef USE_MAP
	vec4 sampledDiffuseColor = texture2D( map, vMapUv );
	#ifdef DECODE_VIDEO_TEXTURE
		sampledDiffuseColor = sRGBTransferEOTF( sampledDiffuseColor );
	#endif
	diffuseColor *= sampledDiffuseColor;
#endif`,Qm=`#ifdef USE_MAP
	uniform sampler2D map;
#endif`,t0=`#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
	#if defined( USE_POINTS_UV )
		vec2 uv = vUv;
	#else
		vec2 uv = ( uvTransform * vec3( gl_PointCoord.x, 1.0 - gl_PointCoord.y, 1 ) ).xy;
	#endif
#endif
#ifdef USE_MAP
	diffuseColor *= texture2D( map, uv );
#endif
#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, uv ).g;
#endif`,e0=`#if defined( USE_POINTS_UV )
	varying vec2 vUv;
#else
	#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
		uniform mat3 uvTransform;
	#endif
#endif
#ifdef USE_MAP
	uniform sampler2D map;
#endif
#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,n0=`float metalnessFactor = metalness;
#ifdef USE_METALNESSMAP
	vec4 texelMetalness = texture2D( metalnessMap, vMetalnessMapUv );
	metalnessFactor *= texelMetalness.b;
#endif`,i0=`#ifdef USE_METALNESSMAP
	uniform sampler2D metalnessMap;
#endif`,s0=`#ifdef USE_INSTANCING_MORPH
	float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	float morphTargetBaseInfluence = texelFetch( morphTexture, ivec2( 0, gl_InstanceID ), 0 ).r;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		morphTargetInfluences[i] =  texelFetch( morphTexture, ivec2( i + 1, gl_InstanceID ), 0 ).r;
	}
#endif`,r0=`#if defined( USE_MORPHCOLORS )
	vColor *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		#if defined( USE_COLOR_ALPHA )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ) * morphTargetInfluences[ i ];
		#elif defined( USE_COLOR )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ).rgb * morphTargetInfluences[ i ];
		#endif
	}
#endif`,a0=`#ifdef USE_MORPHNORMALS
	objectNormal *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) objectNormal += getMorph( gl_VertexID, i, 1 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,o0=`#ifdef USE_MORPHTARGETS
	#ifndef USE_INSTANCING_MORPH
		uniform float morphTargetBaseInfluence;
		uniform float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	#endif
	uniform sampler2DArray morphTargetsTexture;
	uniform ivec2 morphTargetsTextureSize;
	vec4 getMorph( const in int vertexIndex, const in int morphTargetIndex, const in int offset ) {
		int texelIndex = vertexIndex * MORPHTARGETS_TEXTURE_STRIDE + offset;
		int y = texelIndex / morphTargetsTextureSize.x;
		int x = texelIndex - y * morphTargetsTextureSize.x;
		ivec3 morphUV = ivec3( x, y, morphTargetIndex );
		return texelFetch( morphTargetsTexture, morphUV, 0 );
	}
#endif`,l0=`#ifdef USE_MORPHTARGETS
	transformed *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) transformed += getMorph( gl_VertexID, i, 0 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,c0=`float faceDirection = gl_FrontFacing ? 1.0 : - 1.0;
#ifdef FLAT_SHADED
	vec3 fdx = dFdx( vViewPosition );
	vec3 fdy = dFdy( vViewPosition );
	vec3 normal = normalize( cross( fdx, fdy ) );
#else
	vec3 normal = normalize( vNormal );
	#ifdef DOUBLE_SIDED
		normal *= faceDirection;
	#endif
#endif
#if defined( USE_NORMALMAP_TANGENTSPACE ) || defined( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY )
	#ifdef USE_TANGENT
		mat3 tbn = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn = getTangentFrame( - vViewPosition, normal,
		#if defined( USE_NORMALMAP )
			vNormalMapUv
		#elif defined( USE_CLEARCOAT_NORMALMAP )
			vClearcoatNormalMapUv
		#else
			vUv
		#endif
		);
	#endif
	#ifdef DOUBLE_SIDED
		tbn[0] *= faceDirection;
		tbn[1] *= faceDirection;
	#endif
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	#ifdef USE_TANGENT
		mat3 tbn2 = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn2 = getTangentFrame( - vViewPosition, normal, vClearcoatNormalMapUv );
	#endif
	#ifdef DOUBLE_SIDED
		tbn2[0] *= faceDirection;
		tbn2[1] *= faceDirection;
	#endif
#endif
vec3 nonPerturbedNormal = normal;`,h0=`#ifdef USE_NORMALMAP_OBJECTSPACE
	normal = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	#ifdef FLIP_SIDED
		normal = - normal;
	#endif
	#ifdef DOUBLE_SIDED
		normal = normal * faceDirection;
	#endif
	normal = normalize( normalMatrix * normal );
#elif defined( USE_NORMALMAP_TANGENTSPACE )
	vec3 mapN = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	#if defined( USE_PACKED_NORMALMAP )
		mapN = vec3( mapN.xy, sqrt( saturate( 1.0 - dot( mapN.xy, mapN.xy ) ) ) );
	#endif
	mapN.xy *= normalScale;
	normal = normalize( tbn * mapN );
#elif defined( USE_BUMPMAP )
	normal = perturbNormalArb( - vViewPosition, normal, dHdxy_fwd(), faceDirection );
#endif`,u0=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,d0=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,f0=`#ifndef FLAT_SHADED
	vNormal = normalize( transformedNormal );
	#ifdef USE_TANGENT
		vTangent = normalize( transformedTangent );
		vBitangent = normalize( cross( vNormal, vTangent ) * tangent.w );
		#ifdef FLIP_SIDED
			vBitangent = - vBitangent;
		#endif
	#endif
#endif`,p0=`#ifdef USE_NORMALMAP
	uniform sampler2D normalMap;
	uniform vec2 normalScale;
#endif
#ifdef USE_NORMALMAP_OBJECTSPACE
	uniform mat3 normalMatrix;
#endif
#if ! defined ( USE_TANGENT ) && ( defined ( USE_NORMALMAP_TANGENTSPACE ) || defined ( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY ) )
	mat3 getTangentFrame( vec3 eye_pos, vec3 surf_norm, vec2 uv ) {
		vec3 q0 = dFdx( eye_pos.xyz );
		vec3 q1 = dFdy( eye_pos.xyz );
		vec2 st0 = dFdx( uv.st );
		vec2 st1 = dFdy( uv.st );
		vec3 N = surf_norm;
		vec3 q1perp = cross( q1, N );
		vec3 q0perp = cross( N, q0 );
		vec3 T = q1perp * st0.x + q0perp * st1.x;
		vec3 B = q1perp * st0.y + q0perp * st1.y;
		float det = max( dot( T, T ), dot( B, B ) );
		float scale = ( det == 0.0 ) ? 0.0 : inversesqrt( det );
		return mat3( T * scale, B * scale, N );
	}
#endif`,m0=`#ifdef USE_CLEARCOAT
	vec3 clearcoatNormal = nonPerturbedNormal;
#endif`,g0=`#ifdef USE_CLEARCOAT_NORMALMAP
	vec3 clearcoatMapN = texture2D( clearcoatNormalMap, vClearcoatNormalMapUv ).xyz * 2.0 - 1.0;
	clearcoatMapN.xy *= clearcoatNormalScale;
	clearcoatNormal = normalize( tbn2 * clearcoatMapN );
#endif`,x0=`#ifdef USE_CLEARCOATMAP
	uniform sampler2D clearcoatMap;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform sampler2D clearcoatNormalMap;
	uniform vec2 clearcoatNormalScale;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform sampler2D clearcoatRoughnessMap;
#endif`,_0=`#ifdef USE_IRIDESCENCEMAP
	uniform sampler2D iridescenceMap;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform sampler2D iridescenceThicknessMap;
#endif`,y0=`#ifdef OPAQUE
diffuseColor.a = 1.0;
#endif
#ifdef USE_TRANSMISSION
diffuseColor.a *= material.transmissionAlpha;
#endif
gl_FragColor = vec4( outgoingLight, diffuseColor.a );`,v0=`vec3 packNormalToRGB( const in vec3 normal ) {
	return normalize( normal ) * 0.5 + 0.5;
}
vec3 unpackRGBToNormal( const in vec3 rgb ) {
	return 2.0 * rgb.xyz - 1.0;
}
const float PackUpscale = 256. / 255.;const float UnpackDownscale = 255. / 256.;const float ShiftRight8 = 1. / 256.;
const float Inv255 = 1. / 255.;
const vec4 PackFactors = vec4( 1.0, 256.0, 256.0 * 256.0, 256.0 * 256.0 * 256.0 );
const vec2 UnpackFactors2 = vec2( UnpackDownscale, 1.0 / PackFactors.g );
const vec3 UnpackFactors3 = vec3( UnpackDownscale / PackFactors.rg, 1.0 / PackFactors.b );
const vec4 UnpackFactors4 = vec4( UnpackDownscale / PackFactors.rgb, 1.0 / PackFactors.a );
vec4 packDepthToRGBA( const in float v ) {
	if( v <= 0.0 )
		return vec4( 0., 0., 0., 0. );
	if( v >= 1.0 )
		return vec4( 1., 1., 1., 1. );
	float vuf;
	float af = modf( v * PackFactors.a, vuf );
	float bf = modf( vuf * ShiftRight8, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec4( vuf * Inv255, gf * PackUpscale, bf * PackUpscale, af );
}
vec3 packDepthToRGB( const in float v ) {
	if( v <= 0.0 )
		return vec3( 0., 0., 0. );
	if( v >= 1.0 )
		return vec3( 1., 1., 1. );
	float vuf;
	float bf = modf( v * PackFactors.b, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec3( vuf * Inv255, gf * PackUpscale, bf );
}
vec2 packDepthToRG( const in float v ) {
	if( v <= 0.0 )
		return vec2( 0., 0. );
	if( v >= 1.0 )
		return vec2( 1., 1. );
	float vuf;
	float gf = modf( v * 256., vuf );
	return vec2( vuf * Inv255, gf );
}
float unpackRGBAToDepth( const in vec4 v ) {
	return dot( v, UnpackFactors4 );
}
float unpackRGBToDepth( const in vec3 v ) {
	return dot( v, UnpackFactors3 );
}
float unpackRGToDepth( const in vec2 v ) {
	return v.r * UnpackFactors2.r + v.g * UnpackFactors2.g;
}
vec4 pack2HalfToRGBA( const in vec2 v ) {
	vec4 r = vec4( v.x, fract( v.x * 255.0 ), v.y, fract( v.y * 255.0 ) );
	return vec4( r.x - r.y / 255.0, r.y, r.z - r.w / 255.0, r.w );
}
vec2 unpackRGBATo2Half( const in vec4 v ) {
	return vec2( v.x + ( v.y / 255.0 ), v.z + ( v.w / 255.0 ) );
}
float viewZToOrthographicDepth( const in float viewZ, const in float near, const in float far ) {
	return ( viewZ + near ) / ( near - far );
}
float orthographicDepthToViewZ( const in float depth, const in float near, const in float far ) {
	#ifdef USE_REVERSED_DEPTH_BUFFER
	
		return depth * ( far - near ) - far;
	#else
		return depth * ( near - far ) - near;
	#endif
}
float viewZToPerspectiveDepth( const in float viewZ, const in float near, const in float far ) {
	return ( ( near + viewZ ) * far ) / ( ( far - near ) * viewZ );
}
float perspectiveDepthToViewZ( const in float depth, const in float near, const in float far ) {
	
	#ifdef USE_REVERSED_DEPTH_BUFFER
		return ( near * far ) / ( ( near - far ) * depth - near );
	#else
		return ( near * far ) / ( ( far - near ) * depth - far );
	#endif
}`,b0=`#ifdef PREMULTIPLIED_ALPHA
	gl_FragColor.rgb *= gl_FragColor.a;
#endif`,M0=`vec4 mvPosition = vec4( transformed, 1.0 );
#ifdef USE_BATCHING
	mvPosition = batchingMatrix * mvPosition;
#endif
#ifdef USE_INSTANCING
	mvPosition = instanceMatrix * mvPosition;
#endif
mvPosition = modelViewMatrix * mvPosition;
gl_Position = projectionMatrix * mvPosition;`,S0=`#ifdef DITHERING
	gl_FragColor.rgb = dithering( gl_FragColor.rgb );
#endif`,E0=`#ifdef DITHERING
	vec3 dithering( vec3 color ) {
		float grid_position = rand( gl_FragCoord.xy );
		vec3 dither_shift_RGB = vec3( 0.25 / 255.0, -0.25 / 255.0, 0.25 / 255.0 );
		dither_shift_RGB = mix( 2.0 * dither_shift_RGB, -2.0 * dither_shift_RGB, grid_position );
		return color + dither_shift_RGB;
	}
#endif`,w0=`float roughnessFactor = roughness;
#ifdef USE_ROUGHNESSMAP
	vec4 texelRoughness = texture2D( roughnessMap, vRoughnessMapUv );
	roughnessFactor *= texelRoughness.g;
#endif`,T0=`#ifdef USE_ROUGHNESSMAP
	uniform sampler2D roughnessMap;
#endif`,A0=`#if NUM_SPOT_LIGHT_COORDS > 0
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#if NUM_SPOT_LIGHT_MAPS > 0
	uniform sampler2D spotLightMap[ NUM_SPOT_LIGHT_MAPS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_SUN_LIGHT_SHADOWS > 0
		#define SUN_LIGHT_CASCADES 2
		#if defined( SHADOWMAP_TYPE_PCF )
			uniform sampler2DShadow sunShadowMap[ NUM_SUN_LIGHT_SHADOWS ];
		#else
			uniform sampler2D sunShadowMap[ NUM_SUN_LIGHT_SHADOWS ];
		#endif
		uniform mat4 sunShadowMatrix[ NUM_SUN_LIGHT_SHADOWS * SUN_LIGHT_CASCADES ];
		uniform vec4 sunShadowCascade[ NUM_SUN_LIGHT_SHADOWS * SUN_LIGHT_CASCADES ];
		varying vec4 vSunShadowWorldPosition;
		varying vec3 vSunShadowWorldNormal;
		struct SunLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SunLightShadow sunLightShadows[ NUM_SUN_LIGHT_SHADOWS ];
	#endif
	#if NUM_DIR_LIGHT_SHADOWS > 0
		#if defined( SHADOWMAP_TYPE_PCF )
			uniform sampler2DShadow directionalShadowMap[ NUM_DIR_LIGHT_SHADOWS ];
		#else
			uniform sampler2D directionalShadowMap[ NUM_DIR_LIGHT_SHADOWS ];
		#endif
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		#if defined( SHADOWMAP_TYPE_PCF )
			uniform sampler2DShadow spotShadowMap[ NUM_SPOT_LIGHT_SHADOWS ];
		#else
			uniform sampler2D spotShadowMap[ NUM_SPOT_LIGHT_SHADOWS ];
		#endif
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		#if defined( SHADOWMAP_TYPE_PCF )
			uniform samplerCubeShadow pointShadowMap[ NUM_POINT_LIGHT_SHADOWS ];
		#elif defined( SHADOWMAP_TYPE_BASIC )
			uniform samplerCube pointShadowMap[ NUM_POINT_LIGHT_SHADOWS ];
		#endif
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
	#if defined( SHADOWMAP_TYPE_PCF )
		float interleavedGradientNoise( vec2 position ) {
			return fract( 52.9829189 * fract( dot( position, vec2( 0.06711056, 0.00583715 ) ) ) );
		}
		vec2 vogelDiskSample( int sampleIndex, int samplesCount, float phi ) {
			const float goldenAngle = 2.399963229728653;
			float r = sqrt( ( float( sampleIndex ) + 0.5 ) / float( samplesCount ) );
			float theta = float( sampleIndex ) * goldenAngle + phi;
			return vec2( cos( theta ), sin( theta ) ) * r;
		}
	#endif
	#if defined( SHADOWMAP_TYPE_PCF )
		float getShadow( sampler2DShadow shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord ) {
			float shadow = 1.0;
			shadowCoord.xyz /= shadowCoord.w;
			shadowCoord.z += shadowBias;
			bool inFrustum = shadowCoord.x >= 0.0 && shadowCoord.x <= 1.0 && shadowCoord.y >= 0.0 && shadowCoord.y <= 1.0;
			bool frustumTest = inFrustum && shadowCoord.z <= 1.0;
			if ( frustumTest ) {
				vec2 texelSize = vec2( 1.0 ) / shadowMapSize;
				float radius = shadowRadius * texelSize.x;
				float phi = interleavedGradientNoise( gl_FragCoord.xy ) * PI2;
				shadow = (
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 0, 5, phi ) * radius, shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 1, 5, phi ) * radius, shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 2, 5, phi ) * radius, shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 3, 5, phi ) * radius, shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 4, 5, phi ) * radius, shadowCoord.z ) )
				) * 0.2;
			}
			return mix( 1.0, shadow, shadowIntensity );
		}
	#elif defined( SHADOWMAP_TYPE_VSM )
		float getShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord ) {
			float shadow = 1.0;
			shadowCoord.xyz /= shadowCoord.w;
			#ifdef USE_REVERSED_DEPTH_BUFFER
				shadowCoord.z -= shadowBias;
			#else
				shadowCoord.z += shadowBias;
			#endif
			bool inFrustum = shadowCoord.x >= 0.0 && shadowCoord.x <= 1.0 && shadowCoord.y >= 0.0 && shadowCoord.y <= 1.0;
			bool frustumTest = inFrustum && shadowCoord.z <= 1.0;
			if ( frustumTest ) {
				vec2 distribution = texture2D( shadowMap, shadowCoord.xy ).rg;
				float mean = distribution.x;
				float variance = distribution.y * distribution.y;
				#ifdef USE_REVERSED_DEPTH_BUFFER
					float hard_shadow = step( mean, shadowCoord.z );
				#else
					float hard_shadow = step( shadowCoord.z, mean );
				#endif
				
				if ( hard_shadow == 1.0 ) {
					shadow = 1.0;
				} else {
					variance = max( variance, 0.0000001 );
					float d = shadowCoord.z - mean;
					float p_max = variance / ( variance + d * d );
					p_max = clamp( ( p_max - 0.3 ) / 0.65, 0.0, 1.0 );
					shadow = max( hard_shadow, p_max );
				}
			}
			return mix( 1.0, shadow, shadowIntensity );
		}
	#else
		float getShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord ) {
			float shadow = 1.0;
			shadowCoord.xyz /= shadowCoord.w;
			#ifdef USE_REVERSED_DEPTH_BUFFER
				shadowCoord.z -= shadowBias;
			#else
				shadowCoord.z += shadowBias;
			#endif
			bool inFrustum = shadowCoord.x >= 0.0 && shadowCoord.x <= 1.0 && shadowCoord.y >= 0.0 && shadowCoord.y <= 1.0;
			bool frustumTest = inFrustum && shadowCoord.z <= 1.0;
			if ( frustumTest ) {
				float depth = texture2D( shadowMap, shadowCoord.xy ).r;
				#ifdef USE_REVERSED_DEPTH_BUFFER
					shadow = step( depth, shadowCoord.z );
				#else
					shadow = step( shadowCoord.z, depth );
				#endif
			}
			return mix( 1.0, shadow, shadowIntensity );
		}
	#endif
	#if NUM_SUN_LIGHT_SHADOWS > 0
		float getSunShadow(
			#if defined( SHADOWMAP_TYPE_PCF )
				sampler2DShadow shadowMap,
			#else
				sampler2D shadowMap,
			#endif
			SunLightShadow sunLightShadow,
			int shadowIndex
		) {
			vec4 shadowWorldPosition = vec4( vSunShadowWorldPosition.xyz + vSunShadowWorldNormal * sunLightShadow.shadowNormalBias, 1.0 );
			float viewDepth = vSunShadowWorldPosition.w;
			int cascadeOffset = shadowIndex * SUN_LIGHT_CASCADES;
			float shadow = 1.0;
			for ( int i = SUN_LIGHT_CASCADES - 1; i >= 0; i -- ) {
				vec4 cascade = sunShadowCascade[ cascadeOffset + i ];
				if ( viewDepth >= cascade.x && viewDepth < cascade.y ) {
					float cascadeShadow = getShadow(
						shadowMap,
						sunLightShadow.shadowMapSize,
						sunLightShadow.shadowIntensity,
						sunLightShadow.shadowBias,
						sunLightShadow.shadowRadius,
						sunShadowMatrix[ cascadeOffset + i ] * shadowWorldPosition
					);
					shadow = mix( cascadeShadow, shadow, smoothstep( cascade.z, cascade.y, viewDepth ) );
				}
			}
			return shadow;
		}
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
	#if defined( SHADOWMAP_TYPE_PCF )
	float getPointShadow( samplerCubeShadow shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord, float shadowCameraNear, float shadowCameraFar ) {
		float shadow = 1.0;
		vec3 lightToPosition = shadowCoord.xyz;
		vec3 bd3D = normalize( lightToPosition );
		vec3 absVec = abs( lightToPosition );
		float viewSpaceZ = max( max( absVec.x, absVec.y ), absVec.z );
		if ( viewSpaceZ - shadowCameraFar <= 0.0 && viewSpaceZ - shadowCameraNear >= 0.0 ) {
			#ifdef USE_REVERSED_DEPTH_BUFFER
				float dp = ( shadowCameraNear * ( shadowCameraFar - viewSpaceZ ) ) / ( viewSpaceZ * ( shadowCameraFar - shadowCameraNear ) );
				dp -= shadowBias;
			#else
				float dp = ( shadowCameraFar * ( viewSpaceZ - shadowCameraNear ) ) / ( viewSpaceZ * ( shadowCameraFar - shadowCameraNear ) );
				dp += shadowBias;
			#endif
			float texelSize = shadowRadius / shadowMapSize.x;
			vec3 absDir = abs( bd3D );
			vec3 tangent = absDir.x > absDir.z ? vec3( 0.0, 1.0, 0.0 ) : vec3( 1.0, 0.0, 0.0 );
			tangent = normalize( cross( bd3D, tangent ) );
			vec3 bitangent = cross( bd3D, tangent );
			float phi = interleavedGradientNoise( gl_FragCoord.xy ) * PI2;
			vec2 sample0 = vogelDiskSample( 0, 5, phi );
			vec2 sample1 = vogelDiskSample( 1, 5, phi );
			vec2 sample2 = vogelDiskSample( 2, 5, phi );
			vec2 sample3 = vogelDiskSample( 3, 5, phi );
			vec2 sample4 = vogelDiskSample( 4, 5, phi );
			shadow = (
				texture( shadowMap, vec4( bd3D + ( tangent * sample0.x + bitangent * sample0.y ) * texelSize, dp ) ) +
				texture( shadowMap, vec4( bd3D + ( tangent * sample1.x + bitangent * sample1.y ) * texelSize, dp ) ) +
				texture( shadowMap, vec4( bd3D + ( tangent * sample2.x + bitangent * sample2.y ) * texelSize, dp ) ) +
				texture( shadowMap, vec4( bd3D + ( tangent * sample3.x + bitangent * sample3.y ) * texelSize, dp ) ) +
				texture( shadowMap, vec4( bd3D + ( tangent * sample4.x + bitangent * sample4.y ) * texelSize, dp ) )
			) * 0.2;
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
	#elif defined( SHADOWMAP_TYPE_BASIC )
	float getPointShadow( samplerCube shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord, float shadowCameraNear, float shadowCameraFar ) {
		float shadow = 1.0;
		vec3 lightToPosition = shadowCoord.xyz;
		vec3 absVec = abs( lightToPosition );
		float viewSpaceZ = max( max( absVec.x, absVec.y ), absVec.z );
		if ( viewSpaceZ - shadowCameraFar <= 0.0 && viewSpaceZ - shadowCameraNear >= 0.0 ) {
			float dp = ( shadowCameraFar * ( viewSpaceZ - shadowCameraNear ) ) / ( viewSpaceZ * ( shadowCameraFar - shadowCameraNear ) );
			dp += shadowBias;
			vec3 bd3D = normalize( lightToPosition );
			float depth = textureCube( shadowMap, bd3D ).r;
			#ifdef USE_REVERSED_DEPTH_BUFFER
				depth = 1.0 - depth;
			#endif
			shadow = step( dp, depth );
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
	#endif
	#endif
#endif`,R0=`#if NUM_SPOT_LIGHT_COORDS > 0
	uniform mat4 spotLightMatrix[ NUM_SPOT_LIGHT_COORDS ];
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_SUN_LIGHT_SHADOWS > 0
		varying vec4 vSunShadowWorldPosition;
		varying vec3 vSunShadowWorldNormal;
	#endif
	#if NUM_DIR_LIGHT_SHADOWS > 0
		uniform mat4 directionalShadowMatrix[ NUM_DIR_LIGHT_SHADOWS ];
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		uniform mat4 pointShadowMatrix[ NUM_POINT_LIGHT_SHADOWS ];
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
#endif`,C0=`#if ( defined( USE_SHADOWMAP ) && ( NUM_DIR_LIGHT_SHADOWS > 0 || NUM_SUN_LIGHT_SHADOWS > 0 || NUM_POINT_LIGHT_SHADOWS > 0 ) ) || ( NUM_SPOT_LIGHT_COORDS > 0 )
	#ifdef HAS_NORMAL
		vec3 shadowWorldNormal = transformNormalByInverseViewMatrix( transformedNormal, viewMatrix );
	#else
		vec3 shadowWorldNormal = vec3( 0.0 );
	#endif
	vec4 shadowWorldPosition;
#endif
#if defined( USE_SHADOWMAP )
	#if NUM_SUN_LIGHT_SHADOWS > 0
		vSunShadowWorldPosition = vec4( worldPosition.xyz, - mvPosition.z );
		vSunShadowWorldNormal = shadowWorldNormal;
	#endif
	#if NUM_DIR_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * directionalLightShadows[ i ].shadowNormalBias, 0 );
			vDirectionalShadowCoord[ i ] = directionalShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * pointLightShadows[ i ].shadowNormalBias, 0 );
			vPointShadowCoord[ i ] = pointShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
#endif
#if NUM_SPOT_LIGHT_COORDS > 0
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_COORDS; i ++ ) {
		shadowWorldPosition = worldPosition;
		#if ( defined( USE_SHADOWMAP ) && UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
			shadowWorldPosition.xyz += shadowWorldNormal * spotLightShadows[ i ].shadowNormalBias;
		#endif
		vSpotLightCoord[ i ] = spotLightMatrix[ i ] * shadowWorldPosition;
	}
	#pragma unroll_loop_end
#endif`,P0=`float getShadowMask() {
	float shadow = 1.0;
	#ifdef USE_SHADOWMAP
	#if NUM_SUN_LIGHT_SHADOWS > 0
	SunLightShadow sunLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SUN_LIGHT_SHADOWS; i ++ ) {
		sunLight = sunLightShadows[ i ];
		shadow *= receiveShadow ? getSunShadow( sunShadowMap[ i ], sunLight, UNROLLED_LOOP_INDEX ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
		directionalLight = directionalLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( directionalShadowMap[ i ], directionalLight.shadowMapSize, directionalLight.shadowIntensity, directionalLight.shadowBias, directionalLight.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_SHADOWS; i ++ ) {
		spotLight = spotLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( spotShadowMap[ i ], spotLight.shadowMapSize, spotLight.shadowIntensity, spotLight.shadowBias, spotLight.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0 && ( defined( SHADOWMAP_TYPE_PCF ) || defined( SHADOWMAP_TYPE_BASIC ) )
	PointLightShadow pointLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
		pointLight = pointLightShadows[ i ];
		shadow *= receiveShadow ? getPointShadow( pointShadowMap[ i ], pointLight.shadowMapSize, pointLight.shadowIntensity, pointLight.shadowBias, pointLight.shadowRadius, vPointShadowCoord[ i ], pointLight.shadowCameraNear, pointLight.shadowCameraFar ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#endif
	return shadow;
}`,I0=`#ifdef USE_SKINNING
	mat4 boneMatX = getBoneMatrix( skinIndex.x );
	mat4 boneMatY = getBoneMatrix( skinIndex.y );
	mat4 boneMatZ = getBoneMatrix( skinIndex.z );
	mat4 boneMatW = getBoneMatrix( skinIndex.w );
#endif`,L0=`#ifdef USE_SKINNING
	uniform mat4 bindMatrix;
	uniform mat4 bindMatrixInverse;
	uniform highp sampler2D boneTexture;
	mat4 getBoneMatrix( const in float i ) {
		int size = textureSize( boneTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( boneTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( boneTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( boneTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( boneTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
#endif`,z0=`#ifdef USE_SKINNING
	vec4 skinVertex = bindMatrix * vec4( transformed, 1.0 );
	vec4 skinned = vec4( 0.0 );
	skinned += boneMatX * skinVertex * skinWeight.x;
	skinned += boneMatY * skinVertex * skinWeight.y;
	skinned += boneMatZ * skinVertex * skinWeight.z;
	skinned += boneMatW * skinVertex * skinWeight.w;
	transformed = ( bindMatrixInverse * skinned ).xyz;
#endif`,D0=`#ifdef USE_SKINNING
	mat4 skinMatrix = mat4( 0.0 );
	skinMatrix += skinWeight.x * boneMatX;
	skinMatrix += skinWeight.y * boneMatY;
	skinMatrix += skinWeight.z * boneMatZ;
	skinMatrix += skinWeight.w * boneMatW;
	skinMatrix = bindMatrixInverse * skinMatrix * bindMatrix;
	objectNormal = vec4( skinMatrix * vec4( objectNormal, 0.0 ) ).xyz;
	#ifdef USE_TANGENT
		objectTangent = vec4( skinMatrix * vec4( objectTangent, 0.0 ) ).xyz;
	#endif
#endif`,N0=`float specularStrength;
#ifdef USE_SPECULARMAP
	vec4 texelSpecular = texture2D( specularMap, vSpecularMapUv );
	specularStrength = texelSpecular.r;
#else
	specularStrength = 1.0;
#endif`,U0=`#ifdef USE_SPECULARMAP
	uniform sampler2D specularMap;
#endif`,F0=`#if defined( TONE_MAPPING )
	gl_FragColor.rgb = toneMapping( gl_FragColor.rgb );
#endif`,O0=`#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
uniform float toneMappingExposure;
vec3 LinearToneMapping( vec3 color ) {
	return saturate( toneMappingExposure * color );
}
vec3 ReinhardToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	return saturate( color / ( vec3( 1.0 ) + color ) );
}
vec3 CineonToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	color = max( vec3( 0.0 ), color - 0.004 );
	return pow( ( color * ( 6.2 * color + 0.5 ) ) / ( color * ( 6.2 * color + 1.7 ) + 0.06 ), vec3( 2.2 ) );
}
vec3 RRTAndODTFit( vec3 v ) {
	vec3 a = v * ( v + 0.0245786 ) - 0.000090537;
	vec3 b = v * ( 0.983729 * v + 0.4329510 ) + 0.238081;
	return a / b;
}
vec3 ACESFilmicToneMapping( vec3 color ) {
	const mat3 ACESInputMat = mat3(
		vec3( 0.59719, 0.07600, 0.02840 ),		vec3( 0.35458, 0.90834, 0.13383 ),
		vec3( 0.04823, 0.01566, 0.83777 )
	);
	const mat3 ACESOutputMat = mat3(
		vec3(  1.60475, -0.10208, -0.00327 ),		vec3( -0.53108,  1.10813, -0.07276 ),
		vec3( -0.07367, -0.00605,  1.07602 )
	);
	color *= toneMappingExposure / 0.6;
	color = ACESInputMat * color;
	color = RRTAndODTFit( color );
	color = ACESOutputMat * color;
	return saturate( color );
}
const mat3 LINEAR_REC2020_TO_LINEAR_SRGB = mat3(
	vec3( 1.6605, - 0.1246, - 0.0182 ),
	vec3( - 0.5876, 1.1329, - 0.1006 ),
	vec3( - 0.0728, - 0.0083, 1.1187 )
);
const mat3 LINEAR_SRGB_TO_LINEAR_REC2020 = mat3(
	vec3( 0.6274, 0.0691, 0.0164 ),
	vec3( 0.3293, 0.9195, 0.0880 ),
	vec3( 0.0433, 0.0113, 0.8956 )
);
vec3 agxDefaultContrastApprox( vec3 x ) {
	vec3 x2 = x * x;
	vec3 x4 = x2 * x2;
	return + 15.5 * x4 * x2
		- 40.14 * x4 * x
		+ 31.96 * x4
		- 6.868 * x2 * x
		+ 0.4298 * x2
		+ 0.1191 * x
		- 0.00232;
}
vec3 AgXToneMapping( vec3 color ) {
	const mat3 AgXInsetMatrix = mat3(
		vec3( 0.856627153315983, 0.137318972929847, 0.11189821299995 ),
		vec3( 0.0951212405381588, 0.761241990602591, 0.0767994186031903 ),
		vec3( 0.0482516061458583, 0.101439036467562, 0.811302368396859 )
	);
	const mat3 AgXOutsetMatrix = mat3(
		vec3( 1.1271005818144368, - 0.1413297634984383, - 0.14132976349843826 ),
		vec3( - 0.11060664309660323, 1.157823702216272, - 0.11060664309660294 ),
		vec3( - 0.016493938717834573, - 0.016493938717834257, 1.2519364065950405 )
	);
	const float AgxMinEv = - 12.47393;	const float AgxMaxEv = 4.026069;
	color *= toneMappingExposure;
	color = LINEAR_SRGB_TO_LINEAR_REC2020 * color;
	color = AgXInsetMatrix * color;
	color = max( color, 1e-10 );	color = log2( color );
	color = ( color - AgxMinEv ) / ( AgxMaxEv - AgxMinEv );
	color = clamp( color, 0.0, 1.0 );
	color = agxDefaultContrastApprox( color );
	color = AgXOutsetMatrix * color;
	color = pow( max( vec3( 0.0 ), color ), vec3( 2.2 ) );
	color = LINEAR_REC2020_TO_LINEAR_SRGB * color;
	color = clamp( color, 0.0, 1.0 );
	return color;
}
vec3 NeutralToneMapping( vec3 color ) {
	const float StartCompression = 0.8 - 0.04;
	const float Desaturation = 0.15;
	color *= toneMappingExposure;
	float x = min( color.r, min( color.g, color.b ) );
	float offset = x < 0.08 ? x - 6.25 * x * x : 0.04;
	color -= offset;
	float peak = max( color.r, max( color.g, color.b ) );
	if ( peak < StartCompression ) return color;
	float d = 1. - StartCompression;
	float newPeak = 1. - d * d / ( peak + d - StartCompression );
	color *= newPeak / peak;
	float g = 1. - 1. / ( Desaturation * ( peak - newPeak ) + 1. );
	return mix( color, vec3( newPeak ), g );
}
vec3 CustomToneMapping( vec3 color ) { return color; }`,B0=`#ifdef USE_TRANSMISSION
	material.transmission = transmission;
	material.transmissionAlpha = 1.0;
	material.thickness = thickness;
	material.attenuationDistance = attenuationDistance;
	material.attenuationColor = attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		material.transmission *= texture2D( transmissionMap, vTransmissionMapUv ).r;
	#endif
	#ifdef USE_THICKNESSMAP
		material.thickness *= texture2D( thicknessMap, vThicknessMapUv ).g;
	#endif
	vec3 pos = vWorldPosition;
	vec3 v = normalize( cameraPosition - pos );
	vec3 n = transformNormalByInverseViewMatrix( normal, viewMatrix );
	vec4 transmitted = getIBLVolumeRefraction(
		n, v, material.roughness, material.diffuseContribution, material.specularColorBlended, material.specularF90,
		pos, modelMatrix, viewMatrix, projectionMatrix, material.dispersion, material.ior, material.thickness,
		material.attenuationColor, material.attenuationDistance );
	material.transmissionAlpha = mix( material.transmissionAlpha, transmitted.a, material.transmission );
	totalDiffuse = mix( totalDiffuse, transmitted.rgb, material.transmission );
#endif`,k0=`#ifdef USE_TRANSMISSION
	uniform float transmission;
	uniform float thickness;
	uniform float attenuationDistance;
	uniform vec3 attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		uniform sampler2D transmissionMap;
	#endif
	#ifdef USE_THICKNESSMAP
		uniform sampler2D thicknessMap;
	#endif
	uniform vec2 transmissionSamplerSize;
	uniform sampler2D transmissionSamplerMap;
	uniform mat4 modelMatrix;
	uniform mat4 projectionMatrix;
	varying vec3 vWorldPosition;
	float w0( float a ) {
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - a + 3.0 ) - 3.0 ) + 1.0 );
	}
	float w1( float a ) {
		return ( 1.0 / 6.0 ) * ( a *  a * ( 3.0 * a - 6.0 ) + 4.0 );
	}
	float w2( float a ){
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - 3.0 * a + 3.0 ) + 3.0 ) + 1.0 );
	}
	float w3( float a ) {
		return ( 1.0 / 6.0 ) * ( a * a * a );
	}
	float g0( float a ) {
		return w0( a ) + w1( a );
	}
	float g1( float a ) {
		return w2( a ) + w3( a );
	}
	float h0( float a ) {
		return - 1.0 + w1( a ) / ( w0( a ) + w1( a ) );
	}
	float h1( float a ) {
		return 1.0 + w3( a ) / ( w2( a ) + w3( a ) );
	}
	vec4 bicubic( sampler2D tex, vec2 uv, vec4 texelSize, float lod ) {
		uv = uv * texelSize.zw + 0.5;
		vec2 iuv = floor( uv );
		vec2 fuv = fract( uv );
		float g0x = g0( fuv.x );
		float g1x = g1( fuv.x );
		float h0x = h0( fuv.x );
		float h1x = h1( fuv.x );
		float h0y = h0( fuv.y );
		float h1y = h1( fuv.y );
		vec2 p0 = ( vec2( iuv.x + h0x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p1 = ( vec2( iuv.x + h1x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p2 = ( vec2( iuv.x + h0x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		vec2 p3 = ( vec2( iuv.x + h1x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		return g0( fuv.y ) * ( g0x * textureLod( tex, p0, lod ) + g1x * textureLod( tex, p1, lod ) ) +
			g1( fuv.y ) * ( g0x * textureLod( tex, p2, lod ) + g1x * textureLod( tex, p3, lod ) );
	}
	vec4 textureBicubic( sampler2D sampler, vec2 uv, float lod ) {
		vec2 fLodSize = vec2( textureSize( sampler, int( lod ) ) );
		vec2 cLodSize = vec2( textureSize( sampler, int( lod + 1.0 ) ) );
		vec2 fLodSizeInv = 1.0 / fLodSize;
		vec2 cLodSizeInv = 1.0 / cLodSize;
		vec4 fSample = bicubic( sampler, uv, vec4( fLodSizeInv, fLodSize ), floor( lod ) );
		vec4 cSample = bicubic( sampler, uv, vec4( cLodSizeInv, cLodSize ), ceil( lod ) );
		return mix( fSample, cSample, fract( lod ) );
	}
	vec3 getVolumeTransmissionRay( const in vec3 n, const in vec3 v, const in float thickness, const in float ior, const in mat4 modelMatrix ) {
		vec3 refractionVector = refract( - v, normalize( n ), 1.0 / ior );
		vec3 modelScale;
		modelScale.x = length( vec3( modelMatrix[ 0 ].xyz ) );
		modelScale.y = length( vec3( modelMatrix[ 1 ].xyz ) );
		modelScale.z = length( vec3( modelMatrix[ 2 ].xyz ) );
		return normalize( refractionVector ) * thickness * modelScale;
	}
	float applyIorToRoughness( const in float roughness, const in float ior ) {
		return roughness * clamp( ior * 2.0 - 2.0, 0.0, 1.0 );
	}
	vec4 getTransmissionSample( const in vec2 fragCoord, const in float roughness, const in float ior ) {
		float lod = log2( transmissionSamplerSize.x ) * applyIorToRoughness( roughness, ior );
		return textureBicubic( transmissionSamplerMap, fragCoord.xy, lod );
	}
	vec3 volumeAttenuation( const in float transmissionDistance, const in vec3 attenuationColor, const in float attenuationDistance ) {
		if ( isinf( attenuationDistance ) ) {
			return vec3( 1.0 );
		} else {
			vec3 attenuationCoefficient = -log( attenuationColor ) / attenuationDistance;
			vec3 transmittance = exp( - attenuationCoefficient * transmissionDistance );			return transmittance;
		}
	}
	vec4 getIBLVolumeRefraction( const in vec3 n, const in vec3 v, const in float roughness, const in vec3 diffuseColor,
		const in vec3 specularColor, const in float specularF90, const in vec3 position, const in mat4 modelMatrix,
		const in mat4 viewMatrix, const in mat4 projMatrix, const in float dispersion, const in float ior, const in float thickness,
		const in vec3 attenuationColor, const in float attenuationDistance ) {
		vec4 transmittedLight;
		vec3 transmittance;
		#ifdef USE_DISPERSION
			float halfSpread = ( ior - 1.0 ) * 0.025 * dispersion;
			vec3 iors = vec3( ior - halfSpread, ior, ior + halfSpread );
			for ( int i = 0; i < 3; i ++ ) {
				vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, iors[ i ], modelMatrix );
				vec3 refractedRayExit = position + transmissionRay;
				vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
				vec2 refractionCoords = ndcPos.xy / ndcPos.w;
				refractionCoords += 1.0;
				refractionCoords /= 2.0;
				vec4 transmissionSample = getTransmissionSample( refractionCoords, roughness, iors[ i ] );
				transmittedLight[ i ] = transmissionSample[ i ];
				transmittedLight.a += transmissionSample.a;
				transmittance[ i ] = diffuseColor[ i ] * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance )[ i ];
			}
			transmittedLight.a /= 3.0;
		#else
			vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, ior, modelMatrix );
			vec3 refractedRayExit = position + transmissionRay;
			vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
			vec2 refractionCoords = ndcPos.xy / ndcPos.w;
			refractionCoords += 1.0;
			refractionCoords /= 2.0;
			transmittedLight = getTransmissionSample( refractionCoords, roughness, ior );
			transmittance = diffuseColor * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance );
		#endif
		vec3 attenuatedColor = transmittance * transmittedLight.rgb;
		vec3 F = EnvironmentBRDF( n, v, specularColor, specularF90, roughness );
		float transmittanceFactor = ( transmittance.r + transmittance.g + transmittance.b ) / 3.0;
		return vec4( ( 1.0 - F ) * attenuatedColor, 1.0 - ( 1.0 - transmittedLight.a ) * transmittanceFactor );
	}
#endif`,H0=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_SPECULARMAP
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,V0=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	uniform mat3 mapTransform;
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	uniform mat3 alphaMapTransform;
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	uniform mat3 lightMapTransform;
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	uniform mat3 aoMapTransform;
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	uniform mat3 bumpMapTransform;
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	uniform mat3 normalMapTransform;
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_DISPLACEMENTMAP
	uniform mat3 displacementMapTransform;
	varying vec2 vDisplacementMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	uniform mat3 emissiveMapTransform;
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	uniform mat3 metalnessMapTransform;
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	uniform mat3 roughnessMapTransform;
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	uniform mat3 anisotropyMapTransform;
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	uniform mat3 clearcoatMapTransform;
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform mat3 clearcoatNormalMapTransform;
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform mat3 clearcoatRoughnessMapTransform;
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	uniform mat3 sheenColorMapTransform;
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	uniform mat3 sheenRoughnessMapTransform;
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	uniform mat3 iridescenceMapTransform;
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform mat3 iridescenceThicknessMapTransform;
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SPECULARMAP
	uniform mat3 specularMapTransform;
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	uniform mat3 specularColorMapTransform;
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	uniform mat3 specularIntensityMapTransform;
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,G0=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	vUv = vec3( uv, 1 ).xy;
#endif
#ifdef USE_MAP
	vMapUv = ( mapTransform * vec3( MAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ALPHAMAP
	vAlphaMapUv = ( alphaMapTransform * vec3( ALPHAMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_LIGHTMAP
	vLightMapUv = ( lightMapTransform * vec3( LIGHTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_AOMAP
	vAoMapUv = ( aoMapTransform * vec3( AOMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_BUMPMAP
	vBumpMapUv = ( bumpMapTransform * vec3( BUMPMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_NORMALMAP
	vNormalMapUv = ( normalMapTransform * vec3( NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_DISPLACEMENTMAP
	vDisplacementMapUv = ( displacementMapTransform * vec3( DISPLACEMENTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_EMISSIVEMAP
	vEmissiveMapUv = ( emissiveMapTransform * vec3( EMISSIVEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_METALNESSMAP
	vMetalnessMapUv = ( metalnessMapTransform * vec3( METALNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ROUGHNESSMAP
	vRoughnessMapUv = ( roughnessMapTransform * vec3( ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ANISOTROPYMAP
	vAnisotropyMapUv = ( anisotropyMapTransform * vec3( ANISOTROPYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOATMAP
	vClearcoatMapUv = ( clearcoatMapTransform * vec3( CLEARCOATMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	vClearcoatNormalMapUv = ( clearcoatNormalMapTransform * vec3( CLEARCOAT_NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	vClearcoatRoughnessMapUv = ( clearcoatRoughnessMapTransform * vec3( CLEARCOAT_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCEMAP
	vIridescenceMapUv = ( iridescenceMapTransform * vec3( IRIDESCENCEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	vIridescenceThicknessMapUv = ( iridescenceThicknessMapTransform * vec3( IRIDESCENCE_THICKNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_COLORMAP
	vSheenColorMapUv = ( sheenColorMapTransform * vec3( SHEEN_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	vSheenRoughnessMapUv = ( sheenRoughnessMapTransform * vec3( SHEEN_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULARMAP
	vSpecularMapUv = ( specularMapTransform * vec3( SPECULARMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_COLORMAP
	vSpecularColorMapUv = ( specularColorMapTransform * vec3( SPECULAR_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	vSpecularIntensityMapUv = ( specularIntensityMapTransform * vec3( SPECULAR_INTENSITYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_TRANSMISSIONMAP
	vTransmissionMapUv = ( transmissionMapTransform * vec3( TRANSMISSIONMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_THICKNESSMAP
	vThicknessMapUv = ( thicknessMapTransform * vec3( THICKNESSMAP_UV, 1 ) ).xy;
#endif`,W0=`#if defined( USE_ENVMAP ) || defined( DISTANCE ) || defined ( USE_SHADOWMAP ) || defined ( USE_TRANSMISSION ) || NUM_SPOT_LIGHT_COORDS > 0
	vec4 worldPosition = vec4( transformed, 1.0 );
	#ifdef USE_BATCHING
		worldPosition = batchingMatrix * worldPosition;
	#endif
	#ifdef USE_INSTANCING
		worldPosition = instanceMatrix * worldPosition;
	#endif
	worldPosition = modelMatrix * worldPosition;
#endif`,X0=`varying vec2 vUv;
uniform mat3 uvTransform;
void main() {
	vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	gl_Position = vec4( position.xy, 1.0, 1.0 );
}`,q0=`uniform sampler2D t2D;
uniform float backgroundIntensity;
varying vec2 vUv;
void main() {
	vec4 texColor = texture2D( t2D, vUv );
	#ifdef DECODE_VIDEO_TEXTURE
		texColor = vec4( mix( pow( texColor.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), texColor.rgb * 0.0773993808, vec3( lessThanEqual( texColor.rgb, vec3( 0.04045 ) ) ) ), texColor.w );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,Y0=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,Z0=`#ifdef ENVMAP_TYPE_CUBE
	uniform samplerCube envMap;
#elif defined( ENVMAP_TYPE_CUBE_UV )
	uniform sampler2D envMap;
#endif
uniform float backgroundBlurriness;
uniform float backgroundIntensity;
uniform mat3 backgroundRotation;
varying vec3 vWorldDirection;
#include <cube_uv_reflection_fragment>
void main() {
	#ifdef ENVMAP_TYPE_CUBE
		vec4 texColor = textureCube( envMap, backgroundRotation * vWorldDirection );
	#elif defined( ENVMAP_TYPE_CUBE_UV )
		vec4 texColor = textureCubeUV( envMap, backgroundRotation * vWorldDirection, backgroundBlurriness );
	#else
		vec4 texColor = vec4( 0.0, 0.0, 0.0, 1.0 );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,$0=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,K0=`uniform samplerCube tCube;
uniform float tFlip;
uniform float opacity;
varying vec3 vWorldDirection;
void main() {
	vec4 texColor = textureCube( tCube, vec3( tFlip * vWorldDirection.x, vWorldDirection.yz ) );
	gl_FragColor = texColor;
	gl_FragColor.a *= opacity;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,J0=`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
varying vec2 vHighPrecisionZW;
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vHighPrecisionZW = gl_Position.zw;
}`,j0=`#if DEPTH_PACKING == 3200
	uniform float opacity;
#endif
#include <common>
#include <packing>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
varying vec2 vHighPrecisionZW;
void main() {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#if DEPTH_PACKING == 3200
		diffuseColor.a = opacity;
	#endif
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <logdepthbuf_fragment>
	#ifdef USE_REVERSED_DEPTH_BUFFER
		float fragCoordZ = vHighPrecisionZW[ 0 ] / vHighPrecisionZW[ 1 ];
	#else
		float fragCoordZ = 0.5 * vHighPrecisionZW[ 0 ] / vHighPrecisionZW[ 1 ] + 0.5;
	#endif
	#if DEPTH_PACKING == 3200
		gl_FragColor = vec4( vec3( 1.0 - fragCoordZ ), opacity );
	#elif DEPTH_PACKING == 3201
		gl_FragColor = packDepthToRGBA( fragCoordZ );
	#elif DEPTH_PACKING == 3202
		gl_FragColor = vec4( packDepthToRGB( fragCoordZ ), 1.0 );
	#elif DEPTH_PACKING == 3203
		gl_FragColor = vec4( packDepthToRG( fragCoordZ ), 0.0, 1.0 );
	#endif
}`,Q0=`#define DISTANCE
varying vec3 vWorldPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <worldpos_vertex>
	#include <clipping_planes_vertex>
	vWorldPosition = worldPosition.xyz;
}`,tg=`#define DISTANCE
uniform vec3 referencePosition;
uniform float nearDistance;
uniform float farDistance;
varying vec3 vWorldPosition;
#include <common>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	float dist = length( vWorldPosition - referencePosition );
	dist = ( dist - nearDistance ) / ( farDistance - nearDistance );
	dist = saturate( dist );
	gl_FragColor = vec4( dist, 0.0, 0.0, 1.0 );
}`,eg=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
}`,ng=`uniform sampler2D tEquirect;
varying vec3 vWorldDirection;
#include <common>
void main() {
	vec3 direction = normalize( vWorldDirection );
	vec2 sampleUV = equirectUv( direction );
	gl_FragColor = texture2D( tEquirect, sampleUV );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,ig=`uniform float scale;
attribute float lineDistance;
varying float vLineDistance;
#include <common>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	vLineDistance = scale * lineDistance;
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,sg=`uniform vec3 diffuse;
uniform float opacity;
uniform float dashSize;
uniform float totalSize;
varying float vLineDistance;
#include <common>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	if ( mod( vLineDistance, totalSize ) > dashSize ) {
		discard;
	}
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,rg=`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#if defined ( USE_ENVMAP ) || defined ( USE_SKINNING )
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinbase_vertex>
		#include <skinnormal_vertex>
		#include <defaultnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <fog_vertex>
}`,ag=`uniform vec3 diffuse;
uniform float opacity;
#ifndef FLAT_SHADED
	varying vec3 vNormal;
#endif
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		reflectedLight.indirectDiffuse += lightMapTexel.rgb * lightMapIntensity * RECIPROCAL_PI;
	#else
		reflectedLight.indirectDiffuse += vec3( 1.0 );
	#endif
	#include <aomap_fragment>
	reflectedLight.indirectDiffuse *= diffuseColor.rgb;
	vec3 outgoingLight = reflectedLight.indirectDiffuse;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,og=`#define LAMBERT
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,lg=`#define LAMBERT
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <cube_uv_reflection_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <envmap_physical_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_lambert_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_lambert_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,cg=`#define MATCAP
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <displacementmap_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
	vViewPosition = - mvPosition.xyz;
}`,hg=`#define MATCAP
uniform vec3 diffuse;
uniform float opacity;
uniform sampler2D matcap;
varying vec3 vViewPosition;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	vec3 viewDir = normalize( vViewPosition );
	vec3 x = normalize( vec3( viewDir.z, 0.0, - viewDir.x ) );
	vec3 y = cross( viewDir, x );
	vec2 uv = vec2( dot( x, normal ), dot( y, normal ) ) * 0.495 + 0.5;
	#ifdef USE_MATCAP
		vec4 matcapColor = texture2D( matcap, uv );
	#else
		vec4 matcapColor = vec4( vec3( mix( 0.2, 0.8, uv.y ) ), 1.0 );
	#endif
	vec3 outgoingLight = diffuseColor.rgb * matcapColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,ug=`#define NORMAL
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	vViewPosition = - mvPosition.xyz;
#endif
}`,dg=`#define NORMAL
uniform float opacity;
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <uv_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( 0.0, 0.0, 0.0, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	gl_FragColor = vec4( normalize( normal ) * 0.5 + 0.5, diffuseColor.a );
	#ifdef OPAQUE
		gl_FragColor.a = 1.0;
	#endif
}`,fg=`#define PHONG
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,pg=`#define PHONG
uniform vec3 diffuse;
uniform vec3 emissive;
uniform vec3 specular;
uniform float shininess;
uniform float opacity;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <cube_uv_reflection_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <envmap_physical_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_phong_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_phong_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + reflectedLight.directSpecular + reflectedLight.indirectSpecular + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,mg=`#define STANDARD
varying vec3 vViewPosition;
#ifdef USE_TRANSMISSION
	varying vec3 vWorldPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
#ifdef USE_TRANSMISSION
	vWorldPosition = worldPosition.xyz;
#endif
}`,gg=`#define STANDARD
#ifdef PHYSICAL
	#define IOR
	#define USE_SPECULAR
#endif
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float roughness;
uniform float metalness;
uniform float opacity;
#ifdef IOR
	uniform float ior;
#endif
#ifdef USE_SPECULAR
	uniform float specularIntensity;
	uniform vec3 specularColor;
	#ifdef USE_SPECULAR_COLORMAP
		uniform sampler2D specularColorMap;
	#endif
	#ifdef USE_SPECULAR_INTENSITYMAP
		uniform sampler2D specularIntensityMap;
	#endif
#endif
#ifdef USE_CLEARCOAT
	uniform float clearcoat;
	uniform float clearcoatRoughness;
#endif
#ifdef USE_DISPERSION
	uniform float dispersion;
#endif
#ifdef USE_RETROREFLECTION
	uniform float retroreflectivity;
#endif
#ifdef USE_IRIDESCENCE
	uniform float iridescence;
	uniform float iridescenceIOR;
	uniform float iridescenceThicknessMinimum;
	uniform float iridescenceThicknessMaximum;
#endif
#ifdef USE_SHEEN
	uniform vec3 sheenColor;
	uniform float sheenRoughness;
	#ifdef USE_SHEEN_COLORMAP
		uniform sampler2D sheenColorMap;
	#endif
	#ifdef USE_SHEEN_ROUGHNESSMAP
		uniform sampler2D sheenRoughnessMap;
	#endif
#endif
#ifdef USE_ANISOTROPY
	uniform vec2 anisotropyVector;
	#ifdef USE_ANISOTROPYMAP
		uniform sampler2D anisotropyMap;
	#endif
#endif
varying vec3 vViewPosition;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <iridescence_fragment>
#include <cube_uv_reflection_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_physical_pars_fragment>
#include <fog_pars_fragment>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_physical_pars_fragment>
#include <transmission_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <clearcoat_pars_fragment>
#include <iridescence_pars_fragment>
#include <roughnessmap_pars_fragment>
#include <metalnessmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <roughnessmap_fragment>
	#include <metalnessmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <clearcoat_normal_fragment_begin>
	#include <clearcoat_normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_physical_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 totalDiffuse = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;
	vec3 totalSpecular = reflectedLight.directSpecular + reflectedLight.indirectSpecular;
	#include <transmission_fragment>
	vec3 outgoingLight = totalDiffuse + totalSpecular + totalEmissiveRadiance;
	#ifdef USE_SHEEN
 
		outgoingLight = outgoingLight + sheenSpecularDirect + sheenSpecularIndirect;
 
 	#endif
	#ifdef USE_CLEARCOAT
		float dotNVcc = saturate( dot( geometryClearcoatNormal, geometryViewDir ) );
		vec3 Fcc = F_Schlick( material.clearcoatF0, material.clearcoatF90, dotNVcc );
		outgoingLight = outgoingLight * ( 1.0 - material.clearcoat * Fcc ) + ( clearcoatSpecularDirect + clearcoatSpecularIndirect ) * material.clearcoat;
	#endif
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,xg=`#define TOON
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,_g=`#define TOON
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <gradientmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_toon_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_toon_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,yg=`uniform float size;
uniform float scale;
#include <common>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
#ifdef USE_POINTS_UV
	varying vec2 vUv;
	uniform mat3 uvTransform;
#endif
void main() {
	#ifdef USE_POINTS_UV
		vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	#endif
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	gl_PointSize = size;
	#ifdef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) gl_PointSize *= ( scale / - mvPosition.z );
	#endif
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <fog_vertex>
}`,vg=`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <color_pars_fragment>
#include <map_particle_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_particle_fragment>
	#include <color_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,bg=`#include <common>
#include <batching_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <shadowmap_pars_vertex>
void main() {
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,Mg=`uniform vec3 color;
uniform float opacity;
#include <common>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <logdepthbuf_pars_fragment>
#include <shadowmap_pars_fragment>
#include <shadowmask_pars_fragment>
void main() {
	#include <logdepthbuf_fragment>
	gl_FragColor = vec4( color, opacity * ( 1.0 - getShadowMask() ) );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,Sg=`uniform float rotation;
uniform vec2 center;
#include <common>
#include <uv_pars_vertex>
#include <fog_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	vec4 mvPosition = modelViewMatrix[ 3 ];
	vec2 scale = vec2( length( modelMatrix[ 0 ].xyz ), length( modelMatrix[ 1 ].xyz ) );
	#ifndef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) scale *= - mvPosition.z;
	#endif
	vec2 alignedPosition = ( position.xy - ( center - vec2( 0.5 ) ) ) * scale;
	vec2 rotatedPosition;
	rotatedPosition.x = cos( rotation ) * alignedPosition.x - sin( rotation ) * alignedPosition.y;
	rotatedPosition.y = sin( rotation ) * alignedPosition.x + cos( rotation ) * alignedPosition.y;
	mvPosition.xy += rotatedPosition;
	gl_Position = projectionMatrix * mvPosition;
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,Eg=`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
}`,le={alphahash_fragment:Xp,alphahash_pars_fragment:qp,alphamap_fragment:Yp,alphamap_pars_fragment:Zp,alphatest_fragment:$p,alphatest_pars_fragment:Kp,aomap_fragment:Jp,aomap_pars_fragment:jp,batching_pars_vertex:Qp,batching_vertex:tm,begin_vertex:em,beginnormal_vertex:nm,bsdfs:im,iridescence_fragment:sm,bumpmap_pars_fragment:rm,clipping_planes_fragment:am,clipping_planes_pars_fragment:om,clipping_planes_pars_vertex:lm,clipping_planes_vertex:cm,color_fragment:hm,color_pars_fragment:um,color_pars_vertex:dm,color_vertex:fm,common:pm,cube_uv_reflection_fragment:mm,defaultnormal_vertex:gm,displacementmap_pars_vertex:xm,displacementmap_vertex:_m,emissivemap_fragment:ym,emissivemap_pars_fragment:vm,colorspace_fragment:bm,colorspace_pars_fragment:Mm,envmap_fragment:Sm,envmap_common_pars_fragment:Em,envmap_pars_fragment:wm,envmap_pars_vertex:Tm,envmap_physical_pars_fragment:Fm,envmap_vertex:Am,fog_vertex:Rm,fog_pars_vertex:Cm,fog_fragment:Pm,fog_pars_fragment:Im,gradientmap_pars_fragment:Lm,lightmap_pars_fragment:zm,lights_lambert_fragment:Dm,lights_lambert_pars_fragment:Nm,lights_pars_begin:Um,lights_toon_fragment:Om,lights_toon_pars_fragment:Bm,lights_phong_fragment:km,lights_phong_pars_fragment:Hm,lights_physical_fragment:Vm,lights_physical_pars_fragment:Gm,lights_fragment_begin:Wm,lights_fragment_maps:Xm,lights_fragment_end:qm,lightprobes_pars_fragment:Ym,logdepthbuf_fragment:Zm,logdepthbuf_pars_fragment:$m,logdepthbuf_pars_vertex:Km,logdepthbuf_vertex:Jm,map_fragment:jm,map_pars_fragment:Qm,map_particle_fragment:t0,map_particle_pars_fragment:e0,metalnessmap_fragment:n0,metalnessmap_pars_fragment:i0,morphinstance_vertex:s0,morphcolor_vertex:r0,morphnormal_vertex:a0,morphtarget_pars_vertex:o0,morphtarget_vertex:l0,normal_fragment_begin:c0,normal_fragment_maps:h0,normal_pars_fragment:u0,normal_pars_vertex:d0,normal_vertex:f0,normalmap_pars_fragment:p0,clearcoat_normal_fragment_begin:m0,clearcoat_normal_fragment_maps:g0,clearcoat_pars_fragment:x0,iridescence_pars_fragment:_0,opaque_fragment:y0,packing:v0,premultiplied_alpha_fragment:b0,project_vertex:M0,dithering_fragment:S0,dithering_pars_fragment:E0,roughnessmap_fragment:w0,roughnessmap_pars_fragment:T0,shadowmap_pars_fragment:A0,shadowmap_pars_vertex:R0,shadowmap_vertex:C0,shadowmask_pars_fragment:P0,skinbase_vertex:I0,skinning_pars_vertex:L0,skinning_vertex:z0,skinnormal_vertex:D0,specularmap_fragment:N0,specularmap_pars_fragment:U0,tonemapping_fragment:F0,tonemapping_pars_fragment:O0,transmission_fragment:B0,transmission_pars_fragment:k0,uv_pars_fragment:H0,uv_pars_vertex:V0,uv_vertex:G0,worldpos_vertex:W0,background_vert:X0,background_frag:q0,backgroundCube_vert:Y0,backgroundCube_frag:Z0,cube_vert:$0,cube_frag:K0,depth_vert:J0,depth_frag:j0,distance_vert:Q0,distance_frag:tg,equirect_vert:eg,equirect_frag:ng,linedashed_vert:ig,linedashed_frag:sg,meshbasic_vert:rg,meshbasic_frag:ag,meshlambert_vert:og,meshlambert_frag:lg,meshmatcap_vert:cg,meshmatcap_frag:hg,meshnormal_vert:ug,meshnormal_frag:dg,meshphong_vert:fg,meshphong_frag:pg,meshphysical_vert:mg,meshphysical_frag:gg,meshtoon_vert:xg,meshtoon_frag:_g,points_vert:yg,points_frag:vg,shadow_vert:bg,shadow_frag:Mg,sprite_vert:Sg,sprite_frag:Eg},Dt={common:{diffuse:{value:new $t(16777215)},opacity:{value:1},map:{value:null},mapTransform:{value:new Qt},alphaMap:{value:null},alphaMapTransform:{value:new Qt},alphaTest:{value:0}},specularmap:{specularMap:{value:null},specularMapTransform:{value:new Qt}},envmap:{envMap:{value:null},envMapRotation:{value:new Qt},reflectivity:{value:1},ior:{value:1.5},refractionRatio:{value:.98},dfgLUT:{value:null}},aomap:{aoMap:{value:null},aoMapIntensity:{value:1},aoMapTransform:{value:new Qt}},lightmap:{lightMap:{value:null},lightMapIntensity:{value:1},lightMapTransform:{value:new Qt}},bumpmap:{bumpMap:{value:null},bumpMapTransform:{value:new Qt},bumpScale:{value:1}},normalmap:{normalMap:{value:null},normalMapTransform:{value:new Qt},normalScale:{value:new Xt(1,1)}},displacementmap:{displacementMap:{value:null},displacementMapTransform:{value:new Qt},displacementScale:{value:1},displacementBias:{value:0}},emissivemap:{emissiveMap:{value:null},emissiveMapTransform:{value:new Qt}},metalnessmap:{metalnessMap:{value:null},metalnessMapTransform:{value:new Qt}},roughnessmap:{roughnessMap:{value:null},roughnessMapTransform:{value:new Qt}},gradientmap:{gradientMap:{value:null}},fog:{fogDensity:{value:25e-5},fogNear:{value:1},fogFar:{value:2e3},fogColor:{value:new $t(16777215)}},lights:{ambientLightColor:{value:[]},lightProbe:{value:[]},sunLights:{value:[],properties:{direction:{},color:{}}},sunLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},sunShadowMatrix:{value:[]},sunShadowCascade:{value:[]},directionalLights:{value:[],properties:{direction:{},color:{}}},directionalLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},directionalShadowMatrix:{value:[]},spotLights:{value:[],properties:{color:{},position:{},direction:{},distance:{},coneCos:{},penumbraCos:{},decay:{}}},spotLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},spotLightMap:{value:[]},spotLightMatrix:{value:[]},pointLights:{value:[],properties:{color:{},position:{},decay:{},distance:{}}},pointLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{},shadowCameraNear:{},shadowCameraFar:{}}},pointShadowMatrix:{value:[]},hemisphereLights:{value:[],properties:{direction:{},skyColor:{},groundColor:{}}},rectAreaLights:{value:[],properties:{color:{},position:{},width:{},height:{}}},ltc_1:{value:null},ltc_2:{value:null},probesSH:{value:null},probesMin:{value:new F},probesMax:{value:new F},probesResolution:{value:new F}},points:{diffuse:{value:new $t(16777215)},opacity:{value:1},size:{value:1},scale:{value:1},map:{value:null},alphaMap:{value:null},alphaMapTransform:{value:new Qt},alphaTest:{value:0},uvTransform:{value:new Qt}},sprite:{diffuse:{value:new $t(16777215)},opacity:{value:1},center:{value:new Xt(.5,.5)},rotation:{value:0},map:{value:null},mapTransform:{value:new Qt},alphaMap:{value:null},alphaMapTransform:{value:new Qt},alphaTest:{value:0}}},Pi={basic:{uniforms:yn([Dt.common,Dt.specularmap,Dt.envmap,Dt.aomap,Dt.lightmap,Dt.fog]),vertexShader:le.meshbasic_vert,fragmentShader:le.meshbasic_frag},lambert:{uniforms:yn([Dt.common,Dt.specularmap,Dt.envmap,Dt.aomap,Dt.lightmap,Dt.emissivemap,Dt.bumpmap,Dt.normalmap,Dt.displacementmap,Dt.fog,Dt.lights,{emissive:{value:new $t(0)},envMapIntensity:{value:1}}]),vertexShader:le.meshlambert_vert,fragmentShader:le.meshlambert_frag},phong:{uniforms:yn([Dt.common,Dt.specularmap,Dt.envmap,Dt.aomap,Dt.lightmap,Dt.emissivemap,Dt.bumpmap,Dt.normalmap,Dt.displacementmap,Dt.fog,Dt.lights,{emissive:{value:new $t(0)},specular:{value:new $t(1118481)},shininess:{value:30},envMapIntensity:{value:1}}]),vertexShader:le.meshphong_vert,fragmentShader:le.meshphong_frag},standard:{uniforms:yn([Dt.common,Dt.envmap,Dt.aomap,Dt.lightmap,Dt.emissivemap,Dt.bumpmap,Dt.normalmap,Dt.displacementmap,Dt.roughnessmap,Dt.metalnessmap,Dt.fog,Dt.lights,{emissive:{value:new $t(0)},roughness:{value:1},metalness:{value:0},envMapIntensity:{value:1}}]),vertexShader:le.meshphysical_vert,fragmentShader:le.meshphysical_frag},toon:{uniforms:yn([Dt.common,Dt.aomap,Dt.lightmap,Dt.emissivemap,Dt.bumpmap,Dt.normalmap,Dt.displacementmap,Dt.gradientmap,Dt.fog,Dt.lights,{emissive:{value:new $t(0)}}]),vertexShader:le.meshtoon_vert,fragmentShader:le.meshtoon_frag},matcap:{uniforms:yn([Dt.common,Dt.bumpmap,Dt.normalmap,Dt.displacementmap,Dt.fog,{matcap:{value:null}}]),vertexShader:le.meshmatcap_vert,fragmentShader:le.meshmatcap_frag},points:{uniforms:yn([Dt.points,Dt.fog]),vertexShader:le.points_vert,fragmentShader:le.points_frag},dashed:{uniforms:yn([Dt.common,Dt.fog,{scale:{value:1},dashSize:{value:1},totalSize:{value:2}}]),vertexShader:le.linedashed_vert,fragmentShader:le.linedashed_frag},depth:{uniforms:yn([Dt.common,Dt.displacementmap]),vertexShader:le.depth_vert,fragmentShader:le.depth_frag},normal:{uniforms:yn([Dt.common,Dt.bumpmap,Dt.normalmap,Dt.displacementmap,{opacity:{value:1}}]),vertexShader:le.meshnormal_vert,fragmentShader:le.meshnormal_frag},sprite:{uniforms:yn([Dt.sprite,Dt.fog]),vertexShader:le.sprite_vert,fragmentShader:le.sprite_frag},background:{uniforms:{uvTransform:{value:new Qt},t2D:{value:null},backgroundIntensity:{value:1}},vertexShader:le.background_vert,fragmentShader:le.background_frag},backgroundCube:{uniforms:{envMap:{value:null},backgroundBlurriness:{value:0},backgroundIntensity:{value:1},backgroundRotation:{value:new Qt}},vertexShader:le.backgroundCube_vert,fragmentShader:le.backgroundCube_frag},cube:{uniforms:{tCube:{value:null},tFlip:{value:-1},opacity:{value:1}},vertexShader:le.cube_vert,fragmentShader:le.cube_frag},equirect:{uniforms:{tEquirect:{value:null}},vertexShader:le.equirect_vert,fragmentShader:le.equirect_frag},distance:{uniforms:yn([Dt.common,Dt.displacementmap,{referencePosition:{value:new F},nearDistance:{value:1},farDistance:{value:1e3}}]),vertexShader:le.distance_vert,fragmentShader:le.distance_frag},shadow:{uniforms:yn([Dt.lights,Dt.fog,{color:{value:new $t(0)},opacity:{value:1}}]),vertexShader:le.shadow_vert,fragmentShader:le.shadow_frag}};Pi.physical={uniforms:yn([Pi.standard.uniforms,{clearcoat:{value:0},clearcoatMap:{value:null},clearcoatMapTransform:{value:new Qt},clearcoatNormalMap:{value:null},clearcoatNormalMapTransform:{value:new Qt},clearcoatNormalScale:{value:new Xt(1,1)},clearcoatRoughness:{value:0},clearcoatRoughnessMap:{value:null},clearcoatRoughnessMapTransform:{value:new Qt},dispersion:{value:0},retroreflectivity:{value:0},iridescence:{value:0},iridescenceMap:{value:null},iridescenceMapTransform:{value:new Qt},iridescenceIOR:{value:1.3},iridescenceThicknessMinimum:{value:100},iridescenceThicknessMaximum:{value:400},iridescenceThicknessMap:{value:null},iridescenceThicknessMapTransform:{value:new Qt},sheen:{value:0},sheenColor:{value:new $t(0)},sheenColorMap:{value:null},sheenColorMapTransform:{value:new Qt},sheenRoughness:{value:1},sheenRoughnessMap:{value:null},sheenRoughnessMapTransform:{value:new Qt},transmission:{value:0},transmissionMap:{value:null},transmissionMapTransform:{value:new Qt},transmissionSamplerSize:{value:new Xt},transmissionSamplerMap:{value:null},thickness:{value:0},thicknessMap:{value:null},thicknessMapTransform:{value:new Qt},attenuationDistance:{value:0},attenuationColor:{value:new $t(0)},specularColor:{value:new $t(1,1,1)},specularColorMap:{value:null},specularColorMapTransform:{value:new Qt},specularIntensity:{value:1},specularIntensityMap:{value:null},specularIntensityMapTransform:{value:new Qt},anisotropyVector:{value:new Xt},anisotropyMap:{value:null},anisotropyMapTransform:{value:new Qt}}]),vertexShader:le.meshphysical_vert,fragmentShader:le.meshphysical_frag};var Fl={r:0,b:0,g:0},wg=new ge,Bd=new Qt;Bd.set(-1,0,0,0,1,0,0,0,1);function Tg(i,t,e,n,s,r){let a=new $t(0),l=s===!0?0:1,o,c,h=null,f=0,d=null;function p(b){let A=b.isScene===!0?b.background:null;if(A&&A.isTexture){let v=b.backgroundBlurriness>0;A=t.get(A,v)}return A}function x(b){let A=!1,v=p(b);v===null?m(a,l):v&&v.isColor&&(m(v,1),A=!0);let S=i.xr.getEnvironmentBlendMode();S==="additive"?e.buffers.color.setClear(0,0,0,1,r):S==="alpha-blend"&&e.buffers.color.setClear(0,0,0,0,r),(i.autoClear||A)&&(e.buffers.depth.setTest(!0),e.buffers.depth.setMask(!0),e.buffers.color.setMask(!0),i.clear(i.autoClearColor,i.autoClearDepth,i.autoClearStencil))}function M(b,A){let v=p(A);v&&(v.isCubeTexture||v.mapping===Aa)?(c===void 0&&(c=new kt(new ce(1,1,1),new Vn({name:"BackgroundCubeMaterial",uniforms:Zs(Pi.backgroundCube.uniforms),vertexShader:Pi.backgroundCube.vertexShader,fragmentShader:Pi.backgroundCube.fragmentShader,side:Tn,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),c.geometry.deleteAttribute("normal"),c.geometry.deleteAttribute("uv"),c.onBeforeRender=function(S,E,R){this.matrixWorld.copyPosition(R.matrixWorld)},Object.defineProperty(c.material,"envMap",{get:function(){return this.uniforms.envMap.value}}),n.update(c)),c.material.uniforms.envMap.value=v,c.material.uniforms.backgroundBlurriness.value=A.backgroundBlurriness,c.material.uniforms.backgroundIntensity.value=A.backgroundIntensity,c.material.uniforms.backgroundRotation.value.setFromMatrix4(wg.makeRotationFromEuler(A.backgroundRotation)).transpose(),v.isCubeTexture&&v.isRenderTargetTexture===!1&&c.material.uniforms.backgroundRotation.value.premultiply(Bd),c.material.toneMapped=me.getTransfer(v.colorSpace)!==Ae,(h!==v||f!==v.version||d!==i.toneMapping)&&(c.material.needsUpdate=!0,h=v,f=v.version,d=i.toneMapping),c.layers.enableAll(),b.unshift(c,c.geometry,c.material,0,0,null)):v&&v.isTexture&&(o===void 0&&(o=new kt(new Hs(2,2),new Vn({name:"BackgroundMaterial",uniforms:Zs(Pi.background.uniforms),vertexShader:Pi.background.vertexShader,fragmentShader:Pi.background.fragmentShader,side:vs,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),o.geometry.deleteAttribute("normal"),Object.defineProperty(o.material,"map",{get:function(){return this.uniforms.t2D.value}}),n.update(o)),o.material.uniforms.t2D.value=v,o.material.uniforms.backgroundIntensity.value=A.backgroundIntensity,o.material.toneMapped=me.getTransfer(v.colorSpace)!==Ae,v.matrixAutoUpdate===!0&&v.updateMatrix(),o.material.uniforms.uvTransform.value.copy(v.matrix),(h!==v||f!==v.version||d!==i.toneMapping)&&(o.material.needsUpdate=!0,h=v,f=v.version,d=i.toneMapping),o.layers.enableAll(),b.unshift(o,o.geometry,o.material,0,0,null))}function m(b,A){b.getRGB(Fl,ch(i)),e.buffers.color.setClear(Fl.r,Fl.g,Fl.b,A,r)}function u(){c!==void 0&&(c.geometry.dispose(),c.material.dispose(),c=void 0),o!==void 0&&(o.geometry.dispose(),o.material.dispose(),o=void 0)}return{getClearColor:function(){return a},setClearColor:function(b,A=1){a.set(b),l=A,m(a,l)},getClearAlpha:function(){return l},setClearAlpha:function(b){l=b,m(a,l)},render:x,addToRenderList:M,dispose:u}}function Ag(i,t){let e=i.getParameter(i.MAX_VERTEX_ATTRIBS),n={},s=d(null),r=s,a=!1;function l(C,D,V,U,z){let q=!1,N=f(C,U,V,D);r!==N&&(r=N,c(r.object)),q=p(C,U,V,z),q&&x(C,U,V,z),z!==null&&t.update(z,i.ELEMENT_ARRAY_BUFFER),(q||a)&&(a=!1,v(C,D,V,U),z!==null&&i.bindBuffer(i.ELEMENT_ARRAY_BUFFER,t.get(z).buffer))}function o(){return i.createVertexArray()}function c(C){return i.bindVertexArray(C)}function h(C){return i.deleteVertexArray(C)}function f(C,D,V,U){let z=U.wireframe===!0,q=n[D.id];q===void 0&&(q={},n[D.id]=q);let N=C.isInstancedMesh===!0?C.id:0,G=q[N];G===void 0&&(G={},q[N]=G);let X=G[V.id];X===void 0&&(X={},G[V.id]=X);let K=X[z];return K===void 0&&(K=d(o()),X[z]=K),K}function d(C){let D=[],V=[],U=[];for(let z=0;z<e;z++)D[z]=0,V[z]=0,U[z]=0;return{geometry:null,program:null,wireframe:!1,newAttributes:D,enabledAttributes:V,attributeDivisors:U,object:C,attributes:{},index:null}}function p(C,D,V,U){let z=r.attributes,q=D.attributes,N=0,G=V.getAttributes();for(let X in G)if(G[X].location>=0){let nt=z[X],tt=q[X];if(tt===void 0&&(X==="instanceMatrix"&&C.instanceMatrix&&(tt=C.instanceMatrix),X==="instanceColor"&&C.instanceColor&&(tt=C.instanceColor)),nt===void 0||nt.attribute!==tt||tt&&nt.data!==tt.data)return!0;N++}return r.attributesNum!==N||r.index!==U}function x(C,D,V,U){let z={},q=D.attributes,N=0,G=V.getAttributes();for(let X in G)if(G[X].location>=0){let nt=q[X];nt===void 0&&(X==="instanceMatrix"&&C.instanceMatrix&&(nt=C.instanceMatrix),X==="instanceColor"&&C.instanceColor&&(nt=C.instanceColor));let tt={};tt.attribute=nt,nt&&nt.data&&(tt.data=nt.data),z[X]=tt,N++}r.attributes=z,r.attributesNum=N,r.index=U}function M(){let C=r.newAttributes;for(let D=0,V=C.length;D<V;D++)C[D]=0}function m(C){u(C,0)}function u(C,D){let V=r.newAttributes,U=r.enabledAttributes,z=r.attributeDivisors;V[C]=1,U[C]===0&&(i.enableVertexAttribArray(C),U[C]=1),z[C]!==D&&(i.vertexAttribDivisor(C,D),z[C]=D)}function b(){let C=r.newAttributes,D=r.enabledAttributes;for(let V=0,U=D.length;V<U;V++)D[V]!==C[V]&&(i.disableVertexAttribArray(V),D[V]=0)}function A(C,D,V,U,z,q,N){N===!0?i.vertexAttribIPointer(C,D,V,z,q):i.vertexAttribPointer(C,D,V,U,z,q)}function v(C,D,V,U){M();let z=U.attributes,q=V.getAttributes(),N=D.defaultAttributeValues;for(let G in q){let X=q[G];if(X.location>=0){let K=z[G];if(K===void 0&&(G==="instanceMatrix"&&C.instanceMatrix&&(K=C.instanceMatrix),G==="instanceColor"&&C.instanceColor&&(K=C.instanceColor)),K!==void 0){let nt=K.normalized,tt=K.itemSize,lt=t.get(K);if(lt===void 0)continue;let zt=lt.buffer,Lt=lt.type,gt=lt.bytesPerElement,J=Lt===i.INT||Lt===i.UNSIGNED_INT||K.gpuType===Jo;if(K.isInterleavedBufferAttribute){let et=K.data,pt=et.stride,At=K.offset;if(et.isInstancedInterleavedBuffer){for(let Mt=0;Mt<X.locationSize;Mt++)u(X.location+Mt,et.meshPerAttribute);C.isInstancedMesh!==!0&&U._maxInstanceCount===void 0&&(U._maxInstanceCount=et.meshPerAttribute*et.count)}else for(let Mt=0;Mt<X.locationSize;Mt++)m(X.location+Mt);i.bindBuffer(i.ARRAY_BUFFER,zt);for(let Mt=0;Mt<X.locationSize;Mt++)A(X.location+Mt,tt/X.locationSize,Lt,nt,pt*gt,(At+tt/X.locationSize*Mt)*gt,J)}else{if(K.isInstancedBufferAttribute){for(let et=0;et<X.locationSize;et++)u(X.location+et,K.meshPerAttribute);C.isInstancedMesh!==!0&&U._maxInstanceCount===void 0&&(U._maxInstanceCount=K.meshPerAttribute*K.count)}else for(let et=0;et<X.locationSize;et++)m(X.location+et);i.bindBuffer(i.ARRAY_BUFFER,zt);for(let et=0;et<X.locationSize;et++)A(X.location+et,tt/X.locationSize,Lt,nt,tt*gt,tt/X.locationSize*et*gt,J)}}else if(N!==void 0){let nt=N[G];if(nt!==void 0)switch(nt.length){case 2:i.vertexAttrib2fv(X.location,nt);break;case 3:i.vertexAttrib3fv(X.location,nt);break;case 4:i.vertexAttrib4fv(X.location,nt);break;default:i.vertexAttrib1fv(X.location,nt)}}}}b()}function S(){w();for(let C in n){let D=n[C];for(let V in D){let U=D[V];for(let z in U){let q=U[z];for(let N in q)h(q[N].object),delete q[N];delete U[z]}}delete n[C]}}function E(C){if(n[C.id]===void 0)return;let D=n[C.id];for(let V in D){let U=D[V];for(let z in U){let q=U[z];for(let N in q)h(q[N].object),delete q[N];delete U[z]}}delete n[C.id]}function R(C){for(let D in n){let V=n[D];for(let U in V){let z=V[U];if(z[C.id]===void 0)continue;let q=z[C.id];for(let N in q)h(q[N].object),delete q[N];delete z[C.id]}}}function g(C){for(let D in n){let V=n[D],U=C.isInstancedMesh===!0?C.id:0,z=V[U];if(z!==void 0){for(let q in z){let N=z[q];for(let G in N)h(N[G].object),delete N[G];delete z[q]}delete V[U],Object.keys(V).length===0&&delete n[D]}}}function w(){T(),a=!0,r!==s&&(r=s,c(r.object))}function T(){s.geometry=null,s.program=null,s.wireframe=!1}return{setup:l,reset:w,resetDefaultState:T,dispose:S,releaseStatesOfGeometry:E,releaseStatesOfObject:g,releaseStatesOfProgram:R,initAttributes:M,enableAttribute:m,disableUnusedAttributes:b}}function Rg(i,t,e){let n;function s(o){n=o}function r(o,c){i.drawArrays(n,o,c),e.update(c,n,1)}function a(o,c,h){h!==0&&(i.drawArraysInstanced(n,o,c,h),e.update(c,n,h))}function l(o,c,h){if(h===0)return;t.get("WEBGL_multi_draw").multiDrawArraysWEBGL(n,o,0,c,0,h);let d=0;for(let p=0;p<h;p++)d+=c[p];e.update(d,n,1)}this.setMode=s,this.render=r,this.renderInstances=a,this.renderMultiDraw=l}function Cg(i,t,e,n){let s;function r(){if(s!==void 0)return s;if(t.has("EXT_texture_filter_anisotropic")===!0){let R=t.get("EXT_texture_filter_anisotropic");s=i.getParameter(R.MAX_TEXTURE_MAX_ANISOTROPY_EXT)}else s=0;return s}function a(R){return!(R!==$n&&n.convert(R)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_FORMAT))}function l(R){let g=R===fi&&(t.has("EXT_color_buffer_half_float")||t.has("EXT_color_buffer_float"));return!(R!==Dn&&R!==Zn&&!g&&n.convert(R)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_TYPE))}function o(R){if(R==="highp"){if(i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.HIGH_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.HIGH_FLOAT).precision>0)return"highp";R="mediump"}return R==="mediump"&&i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.MEDIUM_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.MEDIUM_FLOAT).precision>0?"mediump":"lowp"}let c=e.precision!==void 0?e.precision:"highp",h=o(c);h!==c&&(Zt("WebGLRenderer:",c,"not supported, using",h,"instead."),c=h);let f=e.logarithmicDepthBuffer===!0,d=e.reversedDepthBuffer===!0&&t.has("EXT_clip_control");e.reversedDepthBuffer===!0&&d===!1&&Zt("WebGLRenderer: Unable to use reversed depth buffer due to missing EXT_clip_control extension. Fallback to default depth buffer.");let p=i.getParameter(i.MAX_TEXTURE_IMAGE_UNITS),x=i.getParameter(i.MAX_VERTEX_TEXTURE_IMAGE_UNITS),M=i.getParameter(i.MAX_TEXTURE_SIZE),m=i.getParameter(i.MAX_CUBE_MAP_TEXTURE_SIZE),u=i.getParameter(i.MAX_VERTEX_ATTRIBS),b=i.getParameter(i.MAX_VERTEX_UNIFORM_VECTORS),A=i.getParameter(i.MAX_VARYING_VECTORS),v=i.getParameter(i.MAX_FRAGMENT_UNIFORM_VECTORS),S=i.getParameter(i.MAX_SAMPLES),E=i.getParameter(i.SAMPLES);return{isWebGL2:!0,getMaxAnisotropy:r,getMaxPrecision:o,textureFormatReadable:a,textureTypeReadable:l,precision:c,logarithmicDepthBuffer:f,reversedDepthBuffer:d,maxTextures:p,maxVertexTextures:x,maxTextureSize:M,maxCubemapSize:m,maxAttributes:u,maxVertexUniforms:b,maxVaryings:A,maxFragmentUniforms:v,maxSamples:S,samples:E}}function Pg(i){let t=this,e=null,n=0,s=!1,r=!1,a=new Hn,l=new Qt,o={value:null,needsUpdate:!1};this.uniform=o,this.numPlanes=0,this.numIntersection=0,this.init=function(f,d){let p=f.length!==0||d||n!==0||s;return s=d,n=f.length,p},this.beginShadows=function(){r=!0,h(null)},this.endShadows=function(){r=!1},this.setGlobalState=function(f,d){e=h(f,d,0)},this.setState=function(f,d,p){let x=f.clippingPlanes,M=f.clipIntersection,m=f.clipShadows,u=i.get(f);if(!s||x===null||x.length===0||r&&!m)r?h(null):c();else{let b=r?0:n,A=b*4,v=u.clippingState||null;o.value=v,v=h(x,d,A,p);for(let S=0;S!==A;++S)v[S]=e[S];u.clippingState=v,this.numIntersection=M?this.numPlanes:0,this.numPlanes+=b}};function c(){o.value!==e&&(o.value=e,o.needsUpdate=n>0),t.numPlanes=n,t.numIntersection=0}function h(f,d,p,x){let M=f!==null?f.length:0,m=null;if(M!==0){if(m=o.value,x!==!0||m===null){let u=p+M*4,b=d.matrixWorldInverse;l.getNormalMatrix(b),(m===null||m.length<u)&&(m=new Float32Array(u));for(let A=0,v=p;A!==M;++A,v+=4)a.copy(f[A]).applyMatrix4(b,l),a.normal.toArray(m,v),m[v+3]=a.constant}o.value=m,o.needsUpdate=!0}return t.numPlanes=M,t.numIntersection=0,m}}var kr=4,Ig=6,Lg=20,zg=256,Na=new zr,xd=new $t,_h=null,yh=0,vh=0,bh=!1,Dg=new F,$s=new F,Bl=class{constructor(t){this._renderer=t,this._pingPongRenderTarget=null,this._lodMax=0,this._cubeSize=0,this._sizeLods=[],this._lodMeshes=[],this._backgroundBox=null,this._cubemapMaterial=null,this._equirectMaterial=null,this._blurMaterial=null,this._ggxMaterial=null}fromScene(t,e=0,n=.1,s=100,r={}){let{size:a=256,position:l=Dg}=r;_h=this._renderer.getRenderTarget(),yh=this._renderer.getActiveCubeFace(),vh=this._renderer.getActiveMipmapLevel(),bh=this._renderer.xr.enabled,this._renderer.xr.enabled=!1,this._setSize(a);let o=this._allocateTargets();return o.depthBuffer=!0,this._sceneToCubeUV(t,n,s,o,l),e>0&&this._blur(o,0,0,e),this._applyPMREM(o),this._cleanup(o),o}fromEquirectangular(t,e=null){return this._fromTexture(t,e)}fromCubemap(t,e=null){return this._fromTexture(t,e)}compileCubemapShader(){this._cubemapMaterial===null&&(this._cubemapMaterial=vd(),this._compileMaterial(this._cubemapMaterial))}compileEquirectangularShader(){this._equirectMaterial===null&&(this._equirectMaterial=yd(),this._compileMaterial(this._equirectMaterial))}dispose(){this._dispose(),this._cubemapMaterial!==null&&this._cubemapMaterial.dispose(),this._equirectMaterial!==null&&this._equirectMaterial.dispose(),this._backgroundBox!==null&&(this._backgroundBox.geometry.dispose(),this._backgroundBox.material.dispose())}_setSize(t){this._lodMax=Math.floor(Math.log2(t)),this._cubeSize=Math.pow(2,this._lodMax)}_dispose(){this._blurMaterial!==null&&this._blurMaterial.dispose(),this._ggxMaterial!==null&&this._ggxMaterial.dispose(),this._pingPongRenderTarget!==null&&this._pingPongRenderTarget.dispose();for(let t=0;t<this._lodMeshes.length;t++)this._lodMeshes[t].geometry.dispose()}_cleanup(t){this._renderer.setRenderTarget(_h,yh,vh),this._renderer.xr.enabled=bh,t.scissorTest=!1,Br(t,0,0,t.width,t.height)}_fromTexture(t,e){t.mapping===bs||t.mapping===Ys?this._setSize(t.image.length===0?16:t.image[0].width||t.image[0].image.width):this._setSize(t.image.width/4),_h=this._renderer.getRenderTarget(),yh=this._renderer.getActiveCubeFace(),vh=this._renderer.getActiveMipmapLevel(),bh=this._renderer.xr.enabled,this._renderer.xr.enabled=!1;let n=e||this._allocateTargets();return this._textureToCubeUV(t,n),this._applyPMREM(n),this._cleanup(n),n}_allocateTargets(){let t=3*Math.max(this._cubeSize,112),e=4*this._cubeSize,n={magFilter:mn,minFilter:mn,generateMipmaps:!1,type:fi,format:$n,colorSpace:ha,depthBuffer:!1},s=_d(t,e,n);if(this._pingPongRenderTarget===null||this._pingPongRenderTarget.width!==t||this._pingPongRenderTarget.height!==e){this._pingPongRenderTarget!==null&&this._dispose(),this._pingPongRenderTarget=_d(t,e,n);let{_lodMax:r}=this;({lodMeshes:this._lodMeshes,sizeLods:this._sizeLods}=Ng(r)),this._blurMaterial=Fg(r,t,e),this._ggxMaterial=Ug(r,t,e)}return s}_compileMaterial(t){let e=new kt(new je,t);this._renderer.compile(e,Na)}_sceneToCubeUV(t,e,n,s,r){let o=new Je(90,1,e,n),c=[1,-1,1,1,1,1],h=[1,1,1,-1,-1,-1],f=this._renderer,d=f.autoClear,p=f.toneMapping;f.getClearColor(xd),f.toneMapping=ui,f.autoClear=!1,f.state.buffers.depth.getReversed()&&(f.setRenderTarget(s),f.clearDepth(),f.setRenderTarget(null)),this._backgroundBox===null&&(this._backgroundBox=new kt(new ce,new be({name:"PMREM.Background",side:Tn,depthWrite:!1,depthTest:!1})));let M=this._backgroundBox,m=M.material,u=!1,b=t.background;b?b.isColor&&(m.color.copy(b),t.background=null,u=!0):(m.color.copy(xd),u=!0);for(let A=0;A<6;A++){let v=A%3;v===0?(o.up.set(0,c[A],0),o.position.set(r.x,r.y,r.z),o.lookAt(r.x+h[A],r.y,r.z)):v===1?(o.up.set(0,0,c[A]),o.position.set(r.x,r.y,r.z),o.lookAt(r.x,r.y+h[A],r.z)):(o.up.set(0,c[A],0),o.position.set(r.x,r.y,r.z),o.lookAt(r.x,r.y,r.z+h[A]));let S=this._cubeSize;Br(s,v*S,A>2?S:0,S,S),f.setRenderTarget(s),u&&f.render(M,o),f.render(t,o)}f.toneMapping=p,f.autoClear=d,t.background=b}_textureToCubeUV(t,e){let n=this._renderer,s=t.mapping===bs||t.mapping===Ys;s?(this._cubemapMaterial===null&&(this._cubemapMaterial=vd()),this._cubemapMaterial.uniforms.flipEnvMap.value=t.isRenderTargetTexture===!1?-1:1):this._equirectMaterial===null&&(this._equirectMaterial=yd());let r=s?this._cubemapMaterial:this._equirectMaterial,a=this._lodMeshes[0];a.material=r;let l=r.uniforms;l.envMap.value=t;let o=this._cubeSize;Br(e,0,0,3*o,2*o),n.setRenderTarget(e),n.render(a,Na)}_applyPMREM(t){let e=this._renderer,n=e.autoClear;e.autoClear=!1;let s=this._lodMeshes.length;for(let r=1;r<s;r++)this._applyGGXFilter(t,r-1,r);e.autoClear=n}_applyGGXFilter(t,e,n){let s=this._renderer,r=this._pingPongRenderTarget,a=this._ggxMaterial,l=this._lodMeshes[n];l.material=a;let o=a.uniforms,c=n/(this._lodMeshes.length-1),h=e/(this._lodMeshes.length-1),f=Math.sqrt(c*c-h*h),d=c*1.25,p=f*d,{_lodMax:x}=this,M=this._sizeLods[n],m=3*M*(n>x-kr?n-x+kr:0),u=4*(this._cubeSize-M);o.envMap.value=t.texture,o.roughness.value=p,o.mipInt.value=x-e,Br(r,m,u,3*M,2*M),s.setRenderTarget(r),s.render(l,Na),o.envMap.value=r.texture,o.roughness.value=0,o.mipInt.value=x-n,Br(t,m,u,3*M,2*M),s.setRenderTarget(t),s.render(l,Na)}_blur(t,e,n,s){let r=this._pingPongRenderTarget,a=Math.min(s,Math.PI)/Math.SQRT2;this._blurPass(t,r,e,n,a),this._blurPass(r,t,n,n,a)}_blurPass(t,e,n,s,r){let a=this._renderer,l=this._blurMaterial,o=this._lodMeshes[s];o.material=l;let c=l.uniforms;c.envMap.value=t.texture,c.sigma.value=r,c.mipInt.value=this._lodMax-n;let h=this._sizeLods[s],f=3*h*(s>this._lodMax-kr?s-this._lodMax+kr:0),d=4*(this._cubeSize-h);Br(e,f,d,3*h,2*h),a.setRenderTarget(e),a.render(o,Na)}};function Ng(i){let t=[],e=[],n=i,s=i-kr+1+Ig;for(let r=0;r<s;r++){let a=Math.pow(2,n);t.push(a);let l=1/(a-2),o=-l,c=1+l,h=[o,o,c,o,c,c,o,o,c,c,o,c],f=6,d=6,p=3,x=new Float32Array(p*d*f),M=new Float32Array(p*d*f);for(let u=0;u<f;u++){let b=u%3*2/3-1,A=u>2?0:-1,v=[b,A,0,b+2/3,A,0,b+2/3,A+1,0,b,A,0,b+2/3,A+1,0,b,A+1,0];x.set(v,p*d*u);for(let S=0;S<d;S++){let E=h[S*2]*2-1,R=h[S*2+1]*2-1;u===0?$s.set(1,R,E):u===1?$s.set(-E,1,-R):u===2?$s.set(-E,R,1):u===3?$s.set(-1,R,-E):u===4?$s.set(-E,-1,R):$s.set(E,R,-1),$s.toArray(M,(u*d+S)*p)}}let m=new je;m.setAttribute("position",new pn(x,p)),m.setAttribute("outputDirection",new pn(M,p)),e.push(new kt(m,null)),n>kr&&n--}return{lodMeshes:e,sizeLods:t}}function _d(i,t,e){let n=new In(i,t,e);return n.texture.mapping=Aa,n.texture.name="PMREM.cubeUv",n.scissorTest=!0,n}function Br(i,t,e,n,s){i.viewport.set(t,e,n,s),i.scissor.set(t,e,n,s)}function Ug(i,t,e){return new Vn({name:"PMREMGGXConvolution",defines:{GGX_SAMPLES:zg,CUBEUV_TEXEL_WIDTH:1/t,CUBEUV_TEXEL_HEIGHT:1/e,CUBEUV_MAX_MIP:`${i}.0`},uniforms:{envMap:{value:null},roughness:{value:0},mipInt:{value:0}},vertexShader:Hl(),fragmentShader:`

			precision highp float;
			precision highp int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;
			uniform float roughness;
			uniform float mipInt;

			#define ENVMAP_TYPE_CUBE_UV
			#include <cube_uv_reflection_fragment>

			#define PI 3.14159265359

			// Van der Corput radical inverse
			float radicalInverse_VdC(uint bits) {
				bits = (bits << 16u) | (bits >> 16u);
				bits = ((bits & 0x55555555u) << 1u) | ((bits & 0xAAAAAAAAu) >> 1u);
				bits = ((bits & 0x33333333u) << 2u) | ((bits & 0xCCCCCCCCu) >> 2u);
				bits = ((bits & 0x0F0F0F0Fu) << 4u) | ((bits & 0xF0F0F0F0u) >> 4u);
				bits = ((bits & 0x00FF00FFu) << 8u) | ((bits & 0xFF00FF00u) >> 8u);
				return float(bits) * 2.3283064365386963e-10; // / 0x100000000
			}

			// Hammersley sequence
			vec2 hammersley(uint i, uint N) {
				return vec2(float(i) / float(N), radicalInverse_VdC(i));
			}

			// GGX VNDF importance sampling (Eric Heitz 2018)
			// "Sampling the GGX Distribution of Visible Normals"
			// https://jcgt.org/published/0007/04/01/
			vec3 importanceSampleGGX_VNDF(vec2 Xi, vec3 V, float roughness) {
				float alpha = roughness * roughness;

				// Section 4.1: Orthonormal basis
				vec3 T1 = vec3(1.0, 0.0, 0.0);
				vec3 T2 = cross(V, T1);

				// Section 4.2: Parameterization of projected area
				float r = sqrt(Xi.x);
				float phi = 2.0 * PI * Xi.y;
				float t1 = r * cos(phi);
				float t2 = r * sin(phi);
				float s = 0.5 * (1.0 + V.z);
				t2 = (1.0 - s) * sqrt(1.0 - t1 * t1) + s * t2;

				// Section 4.3: Reprojection onto hemisphere
				vec3 Nh = t1 * T1 + t2 * T2 + sqrt(max(0.0, 1.0 - t1 * t1 - t2 * t2)) * V;

				// Section 3.4: Transform back to ellipsoid configuration
				return normalize(vec3(alpha * Nh.x, alpha * Nh.y, max(0.0, Nh.z)));
			}

			void main() {
				vec3 N = normalize(vOutputDirection);
				vec3 V = N; // Assume view direction equals normal for pre-filtering

				vec3 prefilteredColor = vec3(0.0);
				float totalWeight = 0.0;

				// For very low roughness, just sample the environment directly
				if (roughness < 0.001) {
					gl_FragColor = vec4(bilinearCubeUV(envMap, N, mipInt), 1.0);
					return;
				}

				// Tangent space basis for VNDF sampling
				vec3 up = abs(N.z) < 0.999 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);
				vec3 tangent = normalize(cross(up, N));
				vec3 bitangent = cross(N, tangent);

				for(uint i = 0u; i < uint(GGX_SAMPLES); i++) {
					vec2 Xi = hammersley(i, uint(GGX_SAMPLES));

					// For PMREM, V = N, so in tangent space V is always (0, 0, 1)
					vec3 H_tangent = importanceSampleGGX_VNDF(Xi, vec3(0.0, 0.0, 1.0), roughness);

					// Transform H back to world space
					vec3 H = normalize(tangent * H_tangent.x + bitangent * H_tangent.y + N * H_tangent.z);
					vec3 L = normalize(2.0 * dot(V, H) * H - V);

					float NdotL = max(dot(N, L), 0.0);

					if(NdotL > 0.0) {
						// Sample environment at fixed mip level
						// VNDF importance sampling handles the distribution filtering
						vec3 sampleColor = bilinearCubeUV(envMap, L, mipInt);

						// Weight by NdotL for the split-sum approximation
						// VNDF PDF naturally accounts for the visible microfacet distribution
						prefilteredColor += sampleColor * NdotL;
						totalWeight += NdotL;
					}
				}

				if (totalWeight > 0.0) {
					prefilteredColor = prefilteredColor / totalWeight;
				}

				gl_FragColor = vec4(prefilteredColor, 1.0);
			}
		`,blending:Ri,depthTest:!1,depthWrite:!1})}function Fg(i,t,e){return new Vn({name:"SphericalGaussianBlur",defines:{SAMPLES:Lg,CUBEUV_TEXEL_WIDTH:1/t,CUBEUV_TEXEL_HEIGHT:1/e,CUBEUV_MAX_MIP:`${i}.0`},uniforms:{envMap:{value:null},sigma:{value:0},mipInt:{value:0}},vertexShader:Hl(),fragmentShader:`

			precision highp float;
			precision highp int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;
			uniform float sigma;
			uniform float mipInt;

			#define ENVMAP_TYPE_CUBE_UV
			#include <cube_uv_reflection_fragment>

			#define PI 3.14159265359
			#define GOLDEN_ANGLE 2.39996322973

			void main() {

				if ( sigma == 0.0 ) {

					gl_FragColor = vec4( bilinearCubeUV( envMap, vOutputDirection, mipInt ), 1.0 );
					return;

				}

				vec3 outputDirection = normalize( vOutputDirection );

				vec3 up = abs( outputDirection.z ) < 0.999 ? vec3( 0.0, 0.0, 1.0 ) : vec3( 1.0, 0.0, 0.0 );
				vec3 tangent = normalize( cross( up, outputDirection ) );
				vec3 bitangent = cross( outputDirection, tangent );

				// Truncate the kernel at three standard deviations or at the antipode.
				float thetaMax = min( 3.0 * sigma, PI );
				float truncation = 1.0 - exp( - 0.5 * thetaMax * thetaMax / ( sigma * sigma ) );

				vec3 accumColor = vec3( 0.0 );
				float accumWeight = 0.0;

				for ( int i = 0; i < SAMPLES; i ++ ) {

					// Stratified inverse-CDF sampling of the Gaussian, placed on a golden-angle spiral.
					float stratum = ( float( i ) + 0.5 ) / float( SAMPLES );
					float theta = sigma * sqrt( - 2.0 * log( 1.0 - stratum * truncation ) );
					float phi = float( i ) * GOLDEN_ANGLE;

					vec3 offset = cos( phi ) * tangent + sin( phi ) * bitangent;
					vec3 sampleDirection = cos( theta ) * outputDirection + sin( theta ) * offset;

					// Correct the planar sample density to solid angle.
					float weight = sin( theta ) / theta;

					accumColor += weight * bilinearCubeUV( envMap, sampleDirection, mipInt );
					accumWeight += weight;

				}

				gl_FragColor = vec4( accumColor / accumWeight, 1.0 );

			}
		`,blending:Ri,depthTest:!1,depthWrite:!1})}function yd(){return new Vn({name:"EquirectangularToCubeUV",uniforms:{envMap:{value:null}},vertexShader:Hl(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;

			#include <common>

			void main() {

				vec3 outputDirection = normalize( vOutputDirection );
				vec2 uv = equirectUv( outputDirection );

				gl_FragColor = vec4( texture2D ( envMap, uv ).rgb, 1.0 );

			}
		`,blending:Ri,depthTest:!1,depthWrite:!1})}function vd(){return new Vn({name:"CubemapToCubeUV",uniforms:{envMap:{value:null},flipEnvMap:{value:-1}},vertexShader:Hl(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			uniform float flipEnvMap;

			varying vec3 vOutputDirection;

			uniform samplerCube envMap;

			void main() {

				gl_FragColor = textureCube( envMap, vec3( flipEnvMap * vOutputDirection.x, vOutputDirection.yz ) );

			}
		`,blending:Ri,depthTest:!1,depthWrite:!1})}function Hl(){return`

		precision mediump float;
		precision mediump int;

		attribute vec3 outputDirection;

		varying vec3 vOutputDirection;

		void main() {

			vOutputDirection = outputDirection;
			gl_Position = vec4( position, 1.0 );

		}
	`}var kl=class extends In{constructor(t=1,e={}){super(t,t,e),this.isWebGLCubeRenderTarget=!0;let n={width:t,height:t,depth:1},s=[n,n,n,n,n,n];this.texture=new xa(s),this._setTextureOptions(e),this.texture.isRenderTargetTexture=!0}fromEquirectangularTexture(t,e){this.texture.type=e.type,this.texture.colorSpace=e.colorSpace,this.texture.generateMipmaps=e.generateMipmaps,this.texture.minFilter=e.minFilter,this.texture.magFilter=e.magFilter;let n={uniforms:{tEquirect:{value:null}},vertexShader:`

				varying vec3 vWorldDirection;

				vec3 transformDirection( in vec3 dir, in mat4 matrix ) {

					return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );

				}

				void main() {

					vWorldDirection = transformDirection( position, modelMatrix );

					#include <begin_vertex>
					#include <project_vertex>

				}
			`,fragmentShader:`

				uniform sampler2D tEquirect;

				varying vec3 vWorldDirection;

				#include <common>

				void main() {

					vec3 direction = normalize( vWorldDirection );

					vec2 sampleUV = equirectUv( direction );

					gl_FragColor = texture2D( tEquirect, sampleUV );

				}
			`},s=new ce(5,5,5),r=new Vn({name:"CubemapFromEquirect",uniforms:Zs(n.uniforms),vertexShader:n.vertexShader,fragmentShader:n.fragmentShader,side:Tn,blending:Ri});r.uniforms.tEquirect.value=e;let a=new kt(s,r),l=e.minFilter;return e.minFilter===Ms&&(e.minFilter=mn),new Xo(1,10,this).update(t,a),e.minFilter=l,a.geometry.dispose(),a.material.dispose(),this}clear(t,e=!0,n=!0,s=!0){let r=t.getRenderTarget();for(let a=0;a<6;a++)t.setRenderTarget(this,a),t.clear(e,n,s);t.setRenderTarget(r)}};function Og(i){let t=new WeakMap,e=new WeakMap,n=null;function s(d,p=!1){return d==null?null:p?a(d):r(d)}function r(d){if(d&&d.isTexture){let p=d.mapping;if(p===Zo||p===$o)if(t.has(d)){let x=t.get(d).texture;return l(x,d.mapping)}else{let x=d.image;if(x&&x.height>0){let M=new kl(x.height);return M.fromEquirectangularTexture(i,d),t.set(d,M),d.addEventListener("dispose",c),l(M.texture,d.mapping)}else return null}}return d}function a(d){if(d&&d.isTexture){let p=d.mapping,x=p===Zo||p===$o,M=p===bs||p===Ys;if(x||M){let m=e.get(d),u=m!==void 0?m.texture.pmremVersion:0;if(d.isRenderTargetTexture&&d.pmremVersion!==u)return n===null&&(n=new Bl(i)),m=x?n.fromEquirectangular(d,m):n.fromCubemap(d,m),m.texture.pmremVersion=d.pmremVersion,e.set(d,m),m.texture;if(m!==void 0)return m.texture;{let b=d.image;return x&&b&&b.height>0||M&&b&&o(b)?(n===null&&(n=new Bl(i)),m=x?n.fromEquirectangular(d):n.fromCubemap(d),m.texture.pmremVersion=d.pmremVersion,e.set(d,m),d.addEventListener("dispose",h),m.texture):null}}}return d}function l(d,p){return p===Zo?d.mapping=bs:p===$o&&(d.mapping=Ys),d}function o(d){let p=0,x=6;for(let M=0;M<x;M++)d[M]!==void 0&&p++;return p===x}function c(d){let p=d.target;p.removeEventListener("dispose",c);let x=t.get(p);x!==void 0&&(t.delete(p),x.dispose())}function h(d){let p=d.target;p.removeEventListener("dispose",h);let x=e.get(p);x!==void 0&&(e.delete(p),x.dispose())}function f(){t=new WeakMap,e=new WeakMap,n!==null&&(n.dispose(),n=null)}return{get:s,dispose:f}}function Bg(i){let t={};function e(n){if(t[n]!==void 0)return t[n];let s=i.getExtension(n);return t[n]=s,s}return{has:function(n){return e(n)!==null},init:function(){e("EXT_color_buffer_float"),e("WEBGL_clip_cull_distance"),e("OES_texture_float_linear"),e("EXT_color_buffer_half_float"),e("WEBGL_multisampled_render_to_texture"),e("WEBGL_render_shared_exponent")},get:function(n){let s=e(n);return s===null&&Os("WebGLRenderer: "+n+" extension not supported."),s}}}function kg(i,t,e,n){let s={},r=new WeakMap;function a(f){let d=f.target;d.index!==null&&t.remove(d.index);for(let x in d.attributes)t.remove(d.attributes[x]);d.removeEventListener("dispose",a),delete s[d.id];let p=r.get(d);p&&(t.remove(p),r.delete(d)),n.releaseStatesOfGeometry(d),d.isInstancedBufferGeometry===!0&&delete d._maxInstanceCount,e.memory.geometries--}function l(f,d){return s[d.id]===!0||(d.addEventListener("dispose",a),s[d.id]=!0,e.memory.geometries++),d}function o(f){let d=f.attributes;for(let p in d)t.update(d[p],i.ARRAY_BUFFER)}function c(f){let d=[],p=f.index,x=f.attributes.position,M=0;if(x===void 0)return;if(p!==null){let b=p.array;M=p.version;for(let A=0,v=b.length;A<v;A+=3){let S=b[A+0],E=b[A+1],R=b[A+2];d.push(S,E,E,R,R,S)}}else{let b=x.array;M=x.version;for(let A=0,v=b.length/3-1;A<v;A+=3){let S=A+0,E=A+1,R=A+2;d.push(S,E,E,R,R,S)}}let m=new(x.count>=65535?ma:pa)(d,1);m.version=M;let u=r.get(f);u&&t.remove(u),r.set(f,m)}function h(f){let d=r.get(f);if(d){let p=f.index;p!==null&&d.version<p.version&&c(f)}else c(f);return r.get(f)}return{get:l,update:o,getWireframeAttribute:h}}function Hg(i,t,e){let n;function s(f){n=f}let r,a;function l(f){r=f.type,a=f.bytesPerElement}function o(f,d){i.drawElements(n,d,r,f*a),e.update(d,n,1)}function c(f,d,p){p!==0&&(i.drawElementsInstanced(n,d,r,f*a,p),e.update(d,n,p))}function h(f,d,p){if(p===0)return;t.get("WEBGL_multi_draw").multiDrawElementsWEBGL(n,d,0,r,f,0,p);let M=0;for(let m=0;m<p;m++)M+=d[m];e.update(M,n,1)}this.setMode=s,this.setIndex=l,this.render=o,this.renderInstances=c,this.renderMultiDraw=h}function Vg(i){let t={geometries:0,textures:0},e={frame:0,calls:0,triangles:0,points:0,lines:0};function n(r,a,l){switch(e.calls++,a){case i.TRIANGLES:e.triangles+=l*(r/3);break;case i.LINES:e.lines+=l*(r/2);break;case i.LINE_STRIP:e.lines+=l*(r-1);break;case i.LINE_LOOP:e.lines+=l*r;break;case i.POINTS:e.points+=l*r;break;default:Kt("WebGLInfo: Unknown draw mode:",a);break}}function s(){e.calls=0,e.triangles=0,e.points=0,e.lines=0}return{memory:t,render:e,programs:null,autoReset:!0,reset:s,update:n}}function Gg(i,t,e){let n=new WeakMap,s=new ke;function r(a,l,o){let c=a.morphTargetInfluences,h=l.morphAttributes.position||l.morphAttributes.normal||l.morphAttributes.color,f=h!==void 0?h.length:0,d=n.get(l);if(d===void 0||d.count!==f){let w=function(){R.dispose(),n.delete(l),l.removeEventListener("dispose",w)};d!==void 0&&d.texture.dispose();let p=l.morphAttributes.position!==void 0,x=l.morphAttributes.normal!==void 0,M=l.morphAttributes.color!==void 0,m=l.morphAttributes.position||[],u=l.morphAttributes.normal||[],b=l.morphAttributes.color||[],A=0;p===!0&&(A=1),x===!0&&(A=2),M===!0&&(A=3);let v=l.attributes.position.count*A,S=1;v>t.maxTextureSize&&(S=Math.ceil(v/t.maxTextureSize),v=t.maxTextureSize);let E=new Float32Array(v*S*4*f),R=new fa(E,v,S,f);R.type=Zn,R.needsUpdate=!0;let g=A*4;for(let T=0;T<f;T++){let C=m[T],D=u[T],V=b[T],U=v*S*4*T;for(let z=0;z<C.count;z++){let q=z*g;p===!0&&(s.fromBufferAttribute(C,z),E[U+q+0]=s.x,E[U+q+1]=s.y,E[U+q+2]=s.z,E[U+q+3]=0),x===!0&&(s.fromBufferAttribute(D,z),E[U+q+4]=s.x,E[U+q+5]=s.y,E[U+q+6]=s.z,E[U+q+7]=0),M===!0&&(s.fromBufferAttribute(V,z),E[U+q+8]=s.x,E[U+q+9]=s.y,E[U+q+10]=s.z,E[U+q+11]=V.itemSize===4?s.w:1)}}d={count:f,texture:R,size:new Xt(v,S)},n.set(l,d),l.addEventListener("dispose",w)}if(a.isInstancedMesh===!0&&a.morphTexture!==null)o.getUniforms().setValue(i,"morphTexture",a.morphTexture,e);else{let p=0;for(let M=0;M<c.length;M++)p+=c[M];let x=l.morphTargetsRelative?1:1-p;o.getUniforms().setValue(i,"morphTargetBaseInfluence",x),o.getUniforms().setValue(i,"morphTargetInfluences",c)}o.getUniforms().setValue(i,"morphTargetsTexture",d.texture,e),o.getUniforms().setValue(i,"morphTargetsTextureSize",d.size)}return{update:r}}function Wg(i,t,e,n,s){let r=new WeakMap;function a(c){let h=s.render.frame,f=c.geometry,d=t.get(c,f);if(r.get(d)!==h&&(t.update(d),r.set(d,h)),c.isInstancedMesh&&(c.hasEventListener("dispose",o)===!1&&c.addEventListener("dispose",o),r.get(c)!==h&&(e.update(c.instanceMatrix,i.ARRAY_BUFFER),c.instanceColor!==null&&e.update(c.instanceColor,i.ARRAY_BUFFER),r.set(c,h))),c.isSkinnedMesh){let p=c.skeleton;r.get(p)!==h&&(p.update(),r.set(p,h))}return d}function l(){r=new WeakMap}function o(c){let h=c.target;h.removeEventListener("dispose",o),n.releaseStatesOfObject(h),e.remove(h.instanceMatrix),h.instanceColor!==null&&e.remove(h.instanceColor)}return{update:a,dispose:l}}var Xg={[Yc]:"LINEAR_TONE_MAPPING",[Zc]:"REINHARD_TONE_MAPPING",[$c]:"CINEON_TONE_MAPPING",[qs]:"ACES_FILMIC_TONE_MAPPING",[Jc]:"AGX_TONE_MAPPING",[jc]:"NEUTRAL_TONE_MAPPING",[Kc]:"CUSTOM_TONE_MAPPING"};function qg(i,t,e,n,s,r){let a=new In(t,e,{type:i,depthBuffer:s,stencilBuffer:r,samples:n?4:0,storeMultisampledDepthBuffer:!1,storeMultisampledStencilBuffer:!1,resolveDepthBuffer:!1,resolveStencilBuffer:!1}),l=null,o=null,c=new je;c.setAttribute("position",new Ee([-1,3,0,-1,-1,0,3,-1,0],3)),c.setAttribute("uv",new Ee([0,2,0,0,2,0],2));let h=new Lo({uniforms:{tDiffuse:{value:null}},vertexShader:`
			precision highp float;

			uniform mat4 modelViewMatrix;
			uniform mat4 projectionMatrix;

			attribute vec3 position;
			attribute vec2 uv;

			varying vec2 vUv;

			void main() {
				vUv = uv;
				gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
			}`,fragmentShader:`
			precision highp float;

			uniform sampler2D tDiffuse;

			varying vec2 vUv;

			#include <tonemapping_pars_fragment>
			#include <colorspace_pars_fragment>

			void main() {
				gl_FragColor = texture2D( tDiffuse, vUv );

				#ifdef LINEAR_TONE_MAPPING
					gl_FragColor.rgb = LinearToneMapping( gl_FragColor.rgb );
				#elif defined( REINHARD_TONE_MAPPING )
					gl_FragColor.rgb = ReinhardToneMapping( gl_FragColor.rgb );
				#elif defined( CINEON_TONE_MAPPING )
					gl_FragColor.rgb = CineonToneMapping( gl_FragColor.rgb );
				#elif defined( ACES_FILMIC_TONE_MAPPING )
					gl_FragColor.rgb = ACESFilmicToneMapping( gl_FragColor.rgb );
				#elif defined( AGX_TONE_MAPPING )
					gl_FragColor.rgb = AgXToneMapping( gl_FragColor.rgb );
				#elif defined( NEUTRAL_TONE_MAPPING )
					gl_FragColor.rgb = NeutralToneMapping( gl_FragColor.rgb );
				#elif defined( CUSTOM_TONE_MAPPING )
					gl_FragColor.rgb = CustomToneMapping( gl_FragColor.rgb );
				#endif

				#ifdef SRGB_TRANSFER
					gl_FragColor = sRGBTransferOETF( gl_FragColor );
				#endif
			}`,depthTest:!1,depthWrite:!1}),f=new kt(c,h),d=new zr(-1,1,1,-1,0,1),p=null,x=null,M=!1,m,u=null,b=[],A=!1;this.setSize=function(v,S){a.setSize(v,S),l!==null&&l.setSize(v,S),o!==null&&o.setSize(v,S);for(let E=0;E<b.length;E++){let R=b[E];R.setSize&&R.setSize(v,S)}},this.setEffects=function(v){b=v,A=b.length>0&&b[0].isRenderPass===!0;let S=a.width,E=a.height;b.length>0&&l===null&&(l=new In(S,E,{type:fi,depthBuffer:!1,stencilBuffer:!1}),o=new In(S,E,{type:fi,depthBuffer:!1,stencilBuffer:!1}));for(let R=0;R<b.length;R++){let g=b[R];g.setSize&&g.setSize(S,E)}},this.begin=function(v,S){if(M||v.toneMapping===ui&&b.length===0)return!1;if(u=S,S!==null){let E=S.width,R=S.height;(a.width!==E||a.height!==R)&&this.setSize(E,R)}return A===!1&&v.setRenderTarget(a),m=v.toneMapping,v.toneMapping=ui,!0},this.hasRenderPass=function(){return A},this.end=function(v,S){v.toneMapping=m,M=!0;let E=a,R=l;for(let g=0;g<b.length;g++){let w=b[g];w.enabled!==!1&&(w.render(v,R,E,S),w.needsSwap!==!1&&(E=R,R=R===l?o:l))}if(p!==v.outputColorSpace||x!==v.toneMapping){p=v.outputColorSpace,x=v.toneMapping,h.defines={},me.getTransfer(p)===Ae&&(h.defines.SRGB_TRANSFER="");let g=Xg[x];g&&(h.defines[g]=""),h.needsUpdate=!0}h.uniforms.tDiffuse.value=E.texture,v.setRenderTarget(u),v.render(f,d),u=null,M=!1},this.isCompositing=function(){return M},this.dispose=function(){a.dispose(),l!==null&&l.dispose(),o!==null&&o.dispose(),c.dispose(),h.dispose()}}var kd=new wn,Eh=new ps(1,1),Hd=new fa,Vd=new Co,Gd=new xa,bd=[],Md=[],Sd=new Float32Array(16),Ed=new Float32Array(9),wd=new Float32Array(4);function Gr(i,t,e){let n=i[0];if(n<=0||n>0)return i;let s=t*e,r=bd[s];if(r===void 0&&(r=new Float32Array(s),bd[s]=r),t!==0){n.toArray(r,0);for(let a=1,l=0;a!==t;++a)l+=e,i[a].toArray(r,l)}return r}function Qe(i,t){if(i.length!==t.length)return!1;for(let e=0,n=i.length;e<n;e++)if(i[e]!==t[e])return!1;return!0}function tn(i,t){for(let e=0,n=t.length;e<n;e++)i[e]=t[e]}function Vl(i,t){let e=Md[t];e===void 0&&(e=new Int32Array(t),Md[t]=e);for(let n=0;n!==t;++n)e[n]=i.allocateTextureUnit();return e}function Yg(i,t){let e=this.cache;e[0]!==t&&(i.uniform1f(this.addr,t),e[0]=t)}function Zg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y)&&(i.uniform2f(this.addr,t.x,t.y),e[0]=t.x,e[1]=t.y);else{if(Qe(e,t))return;i.uniform2fv(this.addr,t),tn(e,t)}}function $g(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z)&&(i.uniform3f(this.addr,t.x,t.y,t.z),e[0]=t.x,e[1]=t.y,e[2]=t.z);else if(t.r!==void 0)(e[0]!==t.r||e[1]!==t.g||e[2]!==t.b)&&(i.uniform3f(this.addr,t.r,t.g,t.b),e[0]=t.r,e[1]=t.g,e[2]=t.b);else{if(Qe(e,t))return;i.uniform3fv(this.addr,t),tn(e,t)}}function Kg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z||e[3]!==t.w)&&(i.uniform4f(this.addr,t.x,t.y,t.z,t.w),e[0]=t.x,e[1]=t.y,e[2]=t.z,e[3]=t.w);else{if(Qe(e,t))return;i.uniform4fv(this.addr,t),tn(e,t)}}function Jg(i,t){let e=this.cache,n=t.elements;if(n===void 0){if(Qe(e,t))return;i.uniformMatrix2fv(this.addr,!1,t),tn(e,t)}else{if(Qe(e,n))return;wd.set(n),i.uniformMatrix2fv(this.addr,!1,wd),tn(e,n)}}function jg(i,t){let e=this.cache,n=t.elements;if(n===void 0){if(Qe(e,t))return;i.uniformMatrix3fv(this.addr,!1,t),tn(e,t)}else{if(Qe(e,n))return;Ed.set(n),i.uniformMatrix3fv(this.addr,!1,Ed),tn(e,n)}}function Qg(i,t){let e=this.cache,n=t.elements;if(n===void 0){if(Qe(e,t))return;i.uniformMatrix4fv(this.addr,!1,t),tn(e,t)}else{if(Qe(e,n))return;Sd.set(n),i.uniformMatrix4fv(this.addr,!1,Sd),tn(e,n)}}function tx(i,t){let e=this.cache;e[0]!==t&&(i.uniform1i(this.addr,t),e[0]=t)}function ex(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y)&&(i.uniform2i(this.addr,t.x,t.y),e[0]=t.x,e[1]=t.y);else{if(Qe(e,t))return;i.uniform2iv(this.addr,t),tn(e,t)}}function nx(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z)&&(i.uniform3i(this.addr,t.x,t.y,t.z),e[0]=t.x,e[1]=t.y,e[2]=t.z);else{if(Qe(e,t))return;i.uniform3iv(this.addr,t),tn(e,t)}}function ix(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z||e[3]!==t.w)&&(i.uniform4i(this.addr,t.x,t.y,t.z,t.w),e[0]=t.x,e[1]=t.y,e[2]=t.z,e[3]=t.w);else{if(Qe(e,t))return;i.uniform4iv(this.addr,t),tn(e,t)}}function sx(i,t){let e=this.cache;e[0]!==t&&(i.uniform1ui(this.addr,t),e[0]=t)}function rx(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y)&&(i.uniform2ui(this.addr,t.x,t.y),e[0]=t.x,e[1]=t.y);else{if(Qe(e,t))return;i.uniform2uiv(this.addr,t),tn(e,t)}}function ax(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z)&&(i.uniform3ui(this.addr,t.x,t.y,t.z),e[0]=t.x,e[1]=t.y,e[2]=t.z);else{if(Qe(e,t))return;i.uniform3uiv(this.addr,t),tn(e,t)}}function ox(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z||e[3]!==t.w)&&(i.uniform4ui(this.addr,t.x,t.y,t.z,t.w),e[0]=t.x,e[1]=t.y,e[2]=t.z,e[3]=t.w);else{if(Qe(e,t))return;i.uniform4uiv(this.addr,t),tn(e,t)}}function lx(i,t,e){let n=this.cache,s=e.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s);let r;this.type===i.SAMPLER_2D_SHADOW?(Eh.compareFunction=e.isReversedDepthBuffer()?Ul:Nl,r=Eh):r=kd,e.setTexture2D(t||r,s)}function cx(i,t,e){let n=this.cache,s=e.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s),e.setTexture3D(t||Vd,s)}function hx(i,t,e){let n=this.cache,s=e.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s),e.setTextureCube(t||Gd,s)}function ux(i,t,e){let n=this.cache,s=e.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s),e.setTexture2DArray(t||Hd,s)}function dx(i){switch(i){case 5126:return Yg;case 35664:return Zg;case 35665:return $g;case 35666:return Kg;case 35674:return Jg;case 35675:return jg;case 35676:return Qg;case 5124:case 35670:return tx;case 35667:case 35671:return ex;case 35668:case 35672:return nx;case 35669:case 35673:return ix;case 5125:return sx;case 36294:return rx;case 36295:return ax;case 36296:return ox;case 35678:case 36198:case 36298:case 36306:case 35682:return lx;case 35679:case 36299:case 36307:return cx;case 35680:case 36300:case 36308:case 36293:return hx;case 36289:case 36303:case 36311:case 36292:return ux}}function fx(i,t){i.uniform1fv(this.addr,t)}function px(i,t){let e=Gr(t,this.size,2);i.uniform2fv(this.addr,e)}function mx(i,t){let e=Gr(t,this.size,3);i.uniform3fv(this.addr,e)}function gx(i,t){let e=Gr(t,this.size,4);i.uniform4fv(this.addr,e)}function xx(i,t){let e=Gr(t,this.size,4);i.uniformMatrix2fv(this.addr,!1,e)}function _x(i,t){let e=Gr(t,this.size,9);i.uniformMatrix3fv(this.addr,!1,e)}function yx(i,t){let e=Gr(t,this.size,16);i.uniformMatrix4fv(this.addr,!1,e)}function vx(i,t){i.uniform1iv(this.addr,t)}function bx(i,t){i.uniform2iv(this.addr,t)}function Mx(i,t){i.uniform3iv(this.addr,t)}function Sx(i,t){i.uniform4iv(this.addr,t)}function Ex(i,t){i.uniform1uiv(this.addr,t)}function wx(i,t){i.uniform2uiv(this.addr,t)}function Tx(i,t){i.uniform3uiv(this.addr,t)}function Ax(i,t){i.uniform4uiv(this.addr,t)}function Rx(i,t,e){let n=this.cache,s=t.length,r=Vl(e,s);Qe(n,r)||(i.uniform1iv(this.addr,r),tn(n,r));let a;this.type===i.SAMPLER_2D_SHADOW?a=Eh:a=kd;for(let l=0;l!==s;++l)e.setTexture2D(t[l]||a,r[l])}function Cx(i,t,e){let n=this.cache,s=t.length,r=Vl(e,s);Qe(n,r)||(i.uniform1iv(this.addr,r),tn(n,r));for(let a=0;a!==s;++a)e.setTexture3D(t[a]||Vd,r[a])}function Px(i,t,e){let n=this.cache,s=t.length,r=Vl(e,s);Qe(n,r)||(i.uniform1iv(this.addr,r),tn(n,r));for(let a=0;a!==s;++a)e.setTextureCube(t[a]||Gd,r[a])}function Ix(i,t,e){let n=this.cache,s=t.length,r=Vl(e,s);Qe(n,r)||(i.uniform1iv(this.addr,r),tn(n,r));for(let a=0;a!==s;++a)e.setTexture2DArray(t[a]||Hd,r[a])}function Lx(i){switch(i){case 5126:return fx;case 35664:return px;case 35665:return mx;case 35666:return gx;case 35674:return xx;case 35675:return _x;case 35676:return yx;case 5124:case 35670:return vx;case 35667:case 35671:return bx;case 35668:case 35672:return Mx;case 35669:case 35673:return Sx;case 5125:return Ex;case 36294:return wx;case 36295:return Tx;case 36296:return Ax;case 35678:case 36198:case 36298:case 36306:case 35682:return Rx;case 35679:case 36299:case 36307:return Cx;case 35680:case 36300:case 36308:case 36293:return Px;case 36289:case 36303:case 36311:case 36292:return Ix}}var wh=class{constructor(t,e,n){this.id=t,this.addr=n,this.cache=[],this.type=e.type,this.setValue=dx(e.type)}},Th=class{constructor(t,e,n){this.id=t,this.addr=n,this.cache=[],this.type=e.type,this.size=e.size,this.setValue=Lx(e.type)}},Ah=class{constructor(t){this.id=t,this.seq=[],this.map={}}setValue(t,e,n){let s=this.seq;for(let r=0,a=s.length;r!==a;++r){let l=s[r];l.setValue(t,e[l.id],n)}}},Mh=/(\w+)(\])?(\[|\.)?/g;function Td(i,t){i.seq.push(t),i.map[t.id]=t}function zx(i,t,e){let n=i.name,s=n.length;for(Mh.lastIndex=0;;){let r=Mh.exec(n),a=Mh.lastIndex,l=r[1],o=r[2]==="]",c=r[3];if(o&&(l=l|0),c===void 0||c==="["&&a+2===s){Td(e,c===void 0?new wh(l,i,t):new Th(l,i,t));break}else{let f=e.map[l];f===void 0&&(f=new Ah(l),Td(e,f)),e=f}}}var Hr=class{constructor(t,e){this.seq=[],this.map={};let n=t.getProgramParameter(e,t.ACTIVE_UNIFORMS);for(let a=0;a<n;++a){let l=t.getActiveUniform(e,a),o=t.getUniformLocation(e,l.name);zx(l,o,this)}let s=[],r=[];for(let a of this.seq)a.type===t.SAMPLER_2D_SHADOW||a.type===t.SAMPLER_CUBE_SHADOW||a.type===t.SAMPLER_2D_ARRAY_SHADOW?s.push(a):r.push(a);s.length>0&&(this.seq=s.concat(r))}setValue(t,e,n,s){let r=this.map[e];r!==void 0&&r.setValue(t,n,s)}setOptional(t,e,n){let s=e[n];s!==void 0&&this.setValue(t,n,s)}static upload(t,e,n,s){for(let r=0,a=e.length;r!==a;++r){let l=e[r],o=n[l.id];o.needsUpdate!==!1&&l.setValue(t,o.value,s)}}static seqWithValue(t,e){let n=[];for(let s=0,r=t.length;s!==r;++s){let a=t[s];a.id in e&&n.push(a)}return n}};function Ad(i,t,e){let n=i.createShader(t);return i.shaderSource(n,e),i.compileShader(n),n}var Dx=37297,Nx=0;function Ux(i,t){let e=i.split(`
`),n=[],s=Math.max(t-6,0),r=Math.min(t+6,e.length);for(let a=s;a<r;a++){let l=a+1;n.push(`${l===t?">":" "} ${l}: ${e[a]}`)}return n.join(`
`)}var Rd=new Qt;function Fx(i){me._getMatrix(Rd,me.workingColorSpace,i);let t=`mat3( ${Rd.elements.map(e=>e.toFixed(4))} )`;switch(me.getTransfer(i)){case ua:return[t,"LinearTransferOETF"];case Ae:return[t,"sRGBTransferOETF"];default:return Zt("WebGLProgram: Unsupported color space: ",i),[t,"LinearTransferOETF"]}}function Cd(i,t,e){let n=i.getShaderParameter(t,i.COMPILE_STATUS),r=(i.getShaderInfoLog(t)||"").trim();if(n&&r==="")return"";let a=/ERROR: 0:(\d+)/.exec(r);if(a){let l=parseInt(a[1]);return e.toUpperCase()+`

`+r+`

`+Ux(i.getShaderSource(t),l)}else return r}function Ox(i,t){let e=Fx(t);return[`vec4 ${i}( vec4 value ) {`,`	return ${e[1]}( vec4( value.rgb * ${e[0]}, value.a ) );`,"}"].join(`
`)}var Bx={[Yc]:"Linear",[Zc]:"Reinhard",[$c]:"Cineon",[qs]:"ACESFilmic",[Jc]:"AgX",[jc]:"Neutral",[Kc]:"Custom"};function kx(i,t){let e=Bx[t];return e===void 0?(Zt("WebGLProgram: Unsupported toneMapping:",t),"vec3 "+i+"( vec3 color ) { return LinearToneMapping( color ); }"):"vec3 "+i+"( vec3 color ) { return "+e+"ToneMapping( color ); }"}var Ol=new F;function Hx(){me.getLuminanceCoefficients(Ol);let i=Ol.x.toFixed(4),t=Ol.y.toFixed(4),e=Ol.z.toFixed(4);return["float luminance( const in vec3 rgb ) {",`	const vec3 weights = vec3( ${i}, ${t}, ${e} );`,"	return dot( weights, rgb );","}"].join(`
`)}function Vx(i){return[i.extensionClipCullDistance?"#extension GL_ANGLE_clip_cull_distance : require":"",i.extensionMultiDraw?"#extension GL_ANGLE_multi_draw : require":""].filter(Fa).join(`
`)}function Gx(i){let t=[];for(let e in i){let n=i[e];n!==!1&&t.push("#define "+e+" "+n)}return t.join(`
`)}function Wx(i,t){let e={},n=i.getProgramParameter(t,i.ACTIVE_ATTRIBUTES);for(let s=0;s<n;s++){let r=i.getActiveAttrib(t,s),a=r.name,l=1;r.type===i.FLOAT_MAT2&&(l=2),r.type===i.FLOAT_MAT3&&(l=3),r.type===i.FLOAT_MAT4&&(l=4),e[a]={type:r.type,location:i.getAttribLocation(t,a),locationSize:l}}return e}function Fa(i){return i!==""}function Pd(i,t){let e=t.numSpotLightShadows+t.numSpotLightMaps-t.numSpotLightShadowsWithMaps;return i.replace(/NUM_SUN_LIGHTS/g,t.numSunLights).replace(/NUM_DIR_LIGHTS/g,t.numDirLights).replace(/NUM_SPOT_LIGHTS/g,t.numSpotLights).replace(/NUM_SPOT_LIGHT_MAPS/g,t.numSpotLightMaps).replace(/NUM_SPOT_LIGHT_COORDS/g,e).replace(/NUM_RECT_AREA_LIGHTS/g,t.numRectAreaLights).replace(/NUM_POINT_LIGHTS/g,t.numPointLights).replace(/NUM_HEMI_LIGHTS/g,t.numHemiLights).replace(/NUM_SUN_LIGHT_SHADOWS/g,t.numSunLightShadows).replace(/NUM_DIR_LIGHT_SHADOWS/g,t.numDirLightShadows).replace(/NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS/g,t.numSpotLightShadowsWithMaps).replace(/NUM_SPOT_LIGHT_SHADOWS/g,t.numSpotLightShadows).replace(/NUM_POINT_LIGHT_SHADOWS/g,t.numPointLightShadows)}function Id(i,t){return i.replace(/NUM_CLIPPING_PLANES/g,t.numClippingPlanes).replace(/UNION_CLIPPING_PLANES/g,t.numClippingPlanes-t.numClipIntersection)}var Xx=/^[ \t]*#include +<([\w\d./]+)>/gm;function Rh(i){return i.replace(Xx,Yx)}var qx=new Map;function Yx(i,t){let e=le[t];if(e===void 0){let n=qx.get(t);if(n!==void 0)e=le[n],Zt('WebGLRenderer: Shader chunk "%s" has been deprecated. Use "%s" instead.',t,n);else throw new Error("THREE.WebGLProgram: Can not resolve #include <"+t+">")}return Rh(e)}var Zx=/#pragma unroll_loop_start\s+for\s*\(\s*int\s+i\s*=\s*(\d+)\s*;\s*i\s*<\s*(\d+)\s*;\s*i\s*\+\+\s*\)\s*{([\s\S]+?)}\s+#pragma unroll_loop_end/g;function Ld(i){return i.replace(Zx,$x)}function $x(i,t,e,n){let s="";for(let r=parseInt(t);r<parseInt(e);r++)s+=n.replace(/\[\s*i\s*\]/g,"[ "+r+" ]").replace(/UNROLLED_LOOP_INDEX/g,r);return s}function zd(i){let t=`precision ${i.precision} float;
	precision ${i.precision} int;
	precision ${i.precision} sampler2D;
	precision ${i.precision} samplerCube;
	precision ${i.precision} sampler3D;
	precision ${i.precision} sampler2DArray;
	precision ${i.precision} sampler2DShadow;
	precision ${i.precision} samplerCubeShadow;
	precision ${i.precision} sampler2DArrayShadow;
	precision ${i.precision} isampler2D;
	precision ${i.precision} isampler3D;
	precision ${i.precision} isamplerCube;
	precision ${i.precision} isampler2DArray;
	precision ${i.precision} usampler2D;
	precision ${i.precision} usampler3D;
	precision ${i.precision} usamplerCube;
	precision ${i.precision} usampler2DArray;
	`;return i.precision==="highp"?t+=`
#define HIGH_PRECISION`:i.precision==="mediump"?t+=`
#define MEDIUM_PRECISION`:i.precision==="lowp"&&(t+=`
#define LOW_PRECISION`),t}var Kx={[Zi]:"SHADOWMAP_TYPE_PCF",[Dr]:"SHADOWMAP_TYPE_VSM"};function Jx(i){return Kx[i.shadowMapType]||"SHADOWMAP_TYPE_BASIC"}var jx={[bs]:"ENVMAP_TYPE_CUBE",[Ys]:"ENVMAP_TYPE_CUBE",[Aa]:"ENVMAP_TYPE_CUBE_UV"};function Qx(i){return i.envMap===!1?"ENVMAP_TYPE_CUBE":jx[i.envMapMode]||"ENVMAP_TYPE_CUBE"}var t_={[Ys]:"ENVMAP_MODE_REFRACTION"};function e_(i){return i.envMap===!1?"ENVMAP_MODE_REFLECTION":t_[i.envMapMode]||"ENVMAP_MODE_REFLECTION"}var n_={[qc]:"ENVMAP_BLENDING_MULTIPLY",[Ku]:"ENVMAP_BLENDING_MIX",[Ju]:"ENVMAP_BLENDING_ADD"};function i_(i){return i.envMap===!1?"ENVMAP_BLENDING_NONE":n_[i.combine]||"ENVMAP_BLENDING_NONE"}function s_(i){let t=i.envMapCubeUVHeight;if(t===null)return null;let e=Math.log2(t)-2,n=1/t;return{texelWidth:1/(3*Math.max(Math.pow(2,e),112)),texelHeight:n,maxMip:e}}function r_(i,t,e,n){let s=i.getContext(),r=e.defines,a=e.vertexShader,l=e.fragmentShader,o=Jx(e),c=Qx(e),h=e_(e),f=i_(e),d=s_(e),p=Vx(e),x=Gx(r),M=s.createProgram(),m,u,b=e.glslVersion?"#version "+e.glslVersion+`
`:"";e.isRawShaderMaterial?(m=["#define SHADER_TYPE "+e.shaderType,"#define SHADER_NAME "+e.shaderName,x].filter(Fa).join(`
`),m.length>0&&(m+=`
`),u=["#define SHADER_TYPE "+e.shaderType,"#define SHADER_NAME "+e.shaderName,x].filter(Fa).join(`
`),u.length>0&&(u+=`
`)):(m=[zd(e),"#define SHADER_TYPE "+e.shaderType,"#define SHADER_NAME "+e.shaderName,x,e.extensionClipCullDistance?"#define USE_CLIP_DISTANCE":"",e.batching?"#define USE_BATCHING":"",e.batchingColor?"#define USE_BATCHING_COLOR":"",e.instancing?"#define USE_INSTANCING":"",e.instancingColor?"#define USE_INSTANCING_COLOR":"",e.instancingMorph?"#define USE_INSTANCING_MORPH":"",e.useFog&&e.fog?"#define USE_FOG":"",e.useFog&&e.fogExp2?"#define FOG_EXP2":"",e.map?"#define USE_MAP":"",e.envMap?"#define USE_ENVMAP":"",e.envMap?"#define "+h:"",e.lightMap?"#define USE_LIGHTMAP":"",e.aoMap?"#define USE_AOMAP":"",e.bumpMap?"#define USE_BUMPMAP":"",e.normalMap?"#define USE_NORMALMAP":"",e.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",e.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",e.displacementMap?"#define USE_DISPLACEMENTMAP":"",e.emissiveMap?"#define USE_EMISSIVEMAP":"",e.anisotropy?"#define USE_ANISOTROPY":"",e.anisotropyMap?"#define USE_ANISOTROPYMAP":"",e.clearcoatMap?"#define USE_CLEARCOATMAP":"",e.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",e.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",e.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",e.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",e.specularMap?"#define USE_SPECULARMAP":"",e.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",e.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",e.roughnessMap?"#define USE_ROUGHNESSMAP":"",e.metalnessMap?"#define USE_METALNESSMAP":"",e.alphaMap?"#define USE_ALPHAMAP":"",e.alphaHash?"#define USE_ALPHAHASH":"",e.transmission?"#define USE_TRANSMISSION":"",e.transmissionMap?"#define USE_TRANSMISSIONMAP":"",e.thicknessMap?"#define USE_THICKNESSMAP":"",e.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",e.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",e.mapUv?"#define MAP_UV "+e.mapUv:"",e.alphaMapUv?"#define ALPHAMAP_UV "+e.alphaMapUv:"",e.lightMapUv?"#define LIGHTMAP_UV "+e.lightMapUv:"",e.aoMapUv?"#define AOMAP_UV "+e.aoMapUv:"",e.emissiveMapUv?"#define EMISSIVEMAP_UV "+e.emissiveMapUv:"",e.bumpMapUv?"#define BUMPMAP_UV "+e.bumpMapUv:"",e.normalMapUv?"#define NORMALMAP_UV "+e.normalMapUv:"",e.displacementMapUv?"#define DISPLACEMENTMAP_UV "+e.displacementMapUv:"",e.metalnessMapUv?"#define METALNESSMAP_UV "+e.metalnessMapUv:"",e.roughnessMapUv?"#define ROUGHNESSMAP_UV "+e.roughnessMapUv:"",e.anisotropyMapUv?"#define ANISOTROPYMAP_UV "+e.anisotropyMapUv:"",e.clearcoatMapUv?"#define CLEARCOATMAP_UV "+e.clearcoatMapUv:"",e.clearcoatNormalMapUv?"#define CLEARCOAT_NORMALMAP_UV "+e.clearcoatNormalMapUv:"",e.clearcoatRoughnessMapUv?"#define CLEARCOAT_ROUGHNESSMAP_UV "+e.clearcoatRoughnessMapUv:"",e.iridescenceMapUv?"#define IRIDESCENCEMAP_UV "+e.iridescenceMapUv:"",e.iridescenceThicknessMapUv?"#define IRIDESCENCE_THICKNESSMAP_UV "+e.iridescenceThicknessMapUv:"",e.sheenColorMapUv?"#define SHEEN_COLORMAP_UV "+e.sheenColorMapUv:"",e.sheenRoughnessMapUv?"#define SHEEN_ROUGHNESSMAP_UV "+e.sheenRoughnessMapUv:"",e.specularMapUv?"#define SPECULARMAP_UV "+e.specularMapUv:"",e.specularColorMapUv?"#define SPECULAR_COLORMAP_UV "+e.specularColorMapUv:"",e.specularIntensityMapUv?"#define SPECULAR_INTENSITYMAP_UV "+e.specularIntensityMapUv:"",e.transmissionMapUv?"#define TRANSMISSIONMAP_UV "+e.transmissionMapUv:"",e.thicknessMapUv?"#define THICKNESSMAP_UV "+e.thicknessMapUv:"",e.vertexTangents&&e.flatShading===!1?"#define USE_TANGENT":"",e.vertexNormals?"#define HAS_NORMAL":"",e.vertexColors?"#define USE_COLOR":"",e.vertexAlphas?"#define USE_COLOR_ALPHA":"",e.vertexUv1s?"#define USE_UV1":"",e.vertexUv2s?"#define USE_UV2":"",e.vertexUv3s?"#define USE_UV3":"",e.pointsUvs?"#define USE_POINTS_UV":"",e.flatShading?"#define FLAT_SHADED":"",e.skinning?"#define USE_SKINNING":"",e.morphTargets?"#define USE_MORPHTARGETS":"",e.morphNormals&&e.flatShading===!1?"#define USE_MORPHNORMALS":"",e.morphColors?"#define USE_MORPHCOLORS":"",e.morphTargetsCount>0?"#define MORPHTARGETS_TEXTURE_STRIDE "+e.morphTextureStride:"",e.morphTargetsCount>0?"#define MORPHTARGETS_COUNT "+e.morphTargetsCount:"",e.doubleSided?"#define DOUBLE_SIDED":"",e.flipSided?"#define FLIP_SIDED":"",e.shadowMapEnabled?"#define USE_SHADOWMAP":"",e.shadowMapEnabled?"#define "+o:"",e.sizeAttenuation?"#define USE_SIZEATTENUATION":"",e.numLightProbes>0?"#define USE_LIGHT_PROBES":"",e.logarithmicDepthBuffer?"#define USE_LOGARITHMIC_DEPTH_BUFFER":"",e.reversedDepthBuffer?"#define USE_REVERSED_DEPTH_BUFFER":"","uniform mat4 modelMatrix;","uniform mat4 modelViewMatrix;","uniform mat4 projectionMatrix;","uniform mat4 viewMatrix;","uniform mat3 normalMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;","#ifdef USE_INSTANCING","	attribute mat4 instanceMatrix;","#endif","#ifdef USE_INSTANCING_COLOR","	attribute vec3 instanceColor;","#endif","#ifdef USE_INSTANCING_MORPH","	uniform sampler2D morphTexture;","#endif","attribute vec3 position;","attribute vec3 normal;","attribute vec2 uv;","#ifdef USE_UV1","	attribute vec2 uv1;","#endif","#ifdef USE_UV2","	attribute vec2 uv2;","#endif","#ifdef USE_UV3","	attribute vec2 uv3;","#endif","#ifdef USE_TANGENT","	attribute vec4 tangent;","#endif","#if defined( USE_COLOR_ALPHA )","	attribute vec4 color;","#elif defined( USE_COLOR )","	attribute vec3 color;","#endif","#ifdef USE_SKINNING","	attribute vec4 skinIndex;","	attribute vec4 skinWeight;","#endif",`
`].filter(Fa).join(`
`),u=[zd(e),"#define SHADER_TYPE "+e.shaderType,"#define SHADER_NAME "+e.shaderName,x,e.useFog&&e.fog?"#define USE_FOG":"",e.useFog&&e.fogExp2?"#define FOG_EXP2":"",e.alphaToCoverage?"#define ALPHA_TO_COVERAGE":"",e.map?"#define USE_MAP":"",e.matcap?"#define USE_MATCAP":"",e.envMap?"#define USE_ENVMAP":"",e.envMap?"#define "+c:"",e.envMap?"#define "+h:"",e.envMap?"#define "+f:"",d?"#define CUBEUV_TEXEL_WIDTH "+d.texelWidth:"",d?"#define CUBEUV_TEXEL_HEIGHT "+d.texelHeight:"",d?"#define CUBEUV_MAX_MIP "+d.maxMip+".0":"",e.lightMap?"#define USE_LIGHTMAP":"",e.aoMap?"#define USE_AOMAP":"",e.bumpMap?"#define USE_BUMPMAP":"",e.normalMap?"#define USE_NORMALMAP":"",e.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",e.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",e.packedNormalMap?"#define USE_PACKED_NORMALMAP":"",e.emissiveMap?"#define USE_EMISSIVEMAP":"",e.anisotropy?"#define USE_ANISOTROPY":"",e.anisotropyMap?"#define USE_ANISOTROPYMAP":"",e.clearcoat?"#define USE_CLEARCOAT":"",e.clearcoatMap?"#define USE_CLEARCOATMAP":"",e.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",e.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",e.dispersion?"#define USE_DISPERSION":"",e.retroreflection?"#define USE_RETROREFLECTION":"",e.iridescence?"#define USE_IRIDESCENCE":"",e.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",e.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",e.specularMap?"#define USE_SPECULARMAP":"",e.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",e.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",e.roughnessMap?"#define USE_ROUGHNESSMAP":"",e.metalnessMap?"#define USE_METALNESSMAP":"",e.alphaMap?"#define USE_ALPHAMAP":"",e.alphaTest?"#define USE_ALPHATEST":"",e.alphaHash?"#define USE_ALPHAHASH":"",e.sheen?"#define USE_SHEEN":"",e.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",e.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",e.transmission?"#define USE_TRANSMISSION":"",e.transmissionMap?"#define USE_TRANSMISSIONMAP":"",e.thicknessMap?"#define USE_THICKNESSMAP":"",e.vertexTangents&&e.flatShading===!1?"#define USE_TANGENT":"",e.vertexColors||e.instancingColor?"#define USE_COLOR":"",e.vertexAlphas||e.batchingColor?"#define USE_COLOR_ALPHA":"",e.vertexUv1s?"#define USE_UV1":"",e.vertexUv2s?"#define USE_UV2":"",e.vertexUv3s?"#define USE_UV3":"",e.pointsUvs?"#define USE_POINTS_UV":"",e.gradientMap?"#define USE_GRADIENTMAP":"",e.flatShading?"#define FLAT_SHADED":"",e.doubleSided?"#define DOUBLE_SIDED":"",e.flipSided?"#define FLIP_SIDED":"",e.shadowMapEnabled?"#define USE_SHADOWMAP":"",e.shadowMapEnabled?"#define "+o:"",e.premultipliedAlpha?"#define PREMULTIPLIED_ALPHA":"",e.numLightProbes>0?"#define USE_LIGHT_PROBES":"",e.numLightProbeGrids>0?"#define USE_LIGHT_PROBES_GRID":"",e.decodeVideoTexture?"#define DECODE_VIDEO_TEXTURE":"",e.decodeVideoTextureEmissive?"#define DECODE_VIDEO_TEXTURE_EMISSIVE":"",e.logarithmicDepthBuffer?"#define USE_LOGARITHMIC_DEPTH_BUFFER":"",e.reversedDepthBuffer?"#define USE_REVERSED_DEPTH_BUFFER":"","uniform mat4 viewMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;",e.toneMapping!==ui?"#define TONE_MAPPING":"",e.toneMapping!==ui?le.tonemapping_pars_fragment:"",e.toneMapping!==ui?kx("toneMapping",e.toneMapping):"",e.dithering?"#define DITHERING":"",e.opaque?"#define OPAQUE":"",le.colorspace_pars_fragment,Ox("linearToOutputTexel",e.outputColorSpace),Hx(),e.useDepthPacking?"#define DEPTH_PACKING "+e.depthPacking:"",`
`].filter(Fa).join(`
`)),a=Rh(a),a=Pd(a,e),a=Id(a,e),l=Rh(l),l=Pd(l,e),l=Id(l,e),a=Ld(a),l=Ld(l),e.isRawShaderMaterial!==!0&&(b=`#version 300 es
`,m=[p,"#define attribute in","#define varying out","#define texture2D texture"].join(`
`)+`
`+m,u=["#define varying in",e.glslVersion===ah?"":"layout(location = 0) out highp vec4 pc_fragColor;",e.glslVersion===ah?"":"#define gl_FragColor pc_fragColor","#define gl_FragDepthEXT gl_FragDepth","#define texture2D texture","#define textureCube texture","#define texture2DProj textureProj","#define texture2DLodEXT textureLod","#define texture2DProjLodEXT textureProjLod","#define textureCubeLodEXT textureLod","#define texture2DGradEXT textureGrad","#define texture2DProjGradEXT textureProjGrad","#define textureCubeGradEXT textureGrad"].join(`
`)+`
`+u);let A=b+m+a,v=b+u+l,S=Ad(s,s.VERTEX_SHADER,A),E=Ad(s,s.FRAGMENT_SHADER,v);s.attachShader(M,S),s.attachShader(M,E),e.index0AttributeName!==void 0?s.bindAttribLocation(M,0,e.index0AttributeName):e.hasPositionAttribute===!0&&s.bindAttribLocation(M,0,"position"),s.linkProgram(M);function R(C){if(i.debug.checkShaderErrors){let D=s.getProgramInfoLog(M)||"",V=s.getShaderInfoLog(S)||"",U=s.getShaderInfoLog(E)||"",z=D.trim(),q=V.trim(),N=U.trim(),G=!0,X=!0;if(s.getProgramParameter(M,s.LINK_STATUS)===!1)if(G=!1,typeof i.debug.onShaderError=="function")i.debug.onShaderError(s,M,S,E);else{let K=Cd(s,S,"vertex"),nt=Cd(s,E,"fragment");Kt("WebGLProgram: Shader Error "+s.getError()+" - VALIDATE_STATUS "+s.getProgramParameter(M,s.VALIDATE_STATUS)+`

Material Name: `+C.name+`
Material Type: `+C.type+`

Program Info Log: `+z+`
`+K+`
`+nt)}else z!==""?Zt("WebGLProgram: Program Info Log:",z):(q===""||N==="")&&(X=!1);X&&(C.diagnostics={runnable:G,programLog:z,vertexShader:{log:q,prefix:m},fragmentShader:{log:N,prefix:u}})}s.deleteShader(S),s.deleteShader(E),g=new Hr(s,M),w=Wx(s,M)}let g;this.getUniforms=function(){return g===void 0&&R(this),g};let w;this.getAttributes=function(){return w===void 0&&R(this),w};let T=e.rendererExtensionParallelShaderCompile===!1;return this.isReady=function(){return T===!1&&(T=s.getProgramParameter(M,Dx)),T},this.destroy=function(){n.releaseStatesOfProgram(this),s.deleteProgram(M),this.program=void 0},this.type=e.shaderType,this.name=e.shaderName,this.id=Nx++,this.cacheKey=t,this.usedTimes=1,this.program=M,this.vertexShader=S,this.fragmentShader=E,this}var a_=0,Ch=class{constructor(){this.shaderCache=new Map,this.materialCache=new Map}update(t,e,n){let s=this._getShaderCacheForMaterial(t);return s.has(e)===!1&&(s.add(e),e.usedTimes++),s.has(n)===!1&&(s.add(n),n.usedTimes++),this}remove(t){let e=this.materialCache.get(t);for(let n of e)n.usedTimes--,n.usedTimes===0&&this.shaderCache.delete(n.code);return this.materialCache.delete(t),this}getVertexShaderStage(t){return this._getShaderStage(t.vertexShader)}getFragmentShaderStage(t){return this._getShaderStage(t.fragmentShader)}dispose(){this.shaderCache.clear(),this.materialCache.clear()}_getShaderCacheForMaterial(t){let e=this.materialCache,n=e.get(t);return n===void 0&&(n=new Set,e.set(t,n)),n}_getShaderStage(t){let e=this.shaderCache,n=e.get(t);return n===void 0&&(n=new Ph(t),e.set(t,n)),n}},Ph=class{constructor(t){this.id=a_++,this.code=t,this.usedTimes=0}};function o_(i){return i===Es||i===za||i===Da}function l_(i,t,e,n,s,r){let a=new Ar,l=new Ch,o=new Set,c=[],h=new Map,f=n.logarithmicDepthBuffer,d=n.precision,p={MeshDepthMaterial:"depth",MeshDistanceMaterial:"distance",MeshNormalMaterial:"normal",MeshBasicMaterial:"basic",MeshLambertMaterial:"lambert",MeshPhongMaterial:"phong",MeshToonMaterial:"toon",MeshStandardMaterial:"physical",MeshPhysicalMaterial:"physical",MeshMatcapMaterial:"matcap",LineBasicMaterial:"basic",LineDashedMaterial:"dashed",PointsMaterial:"points",ShadowMaterial:"shadow",SpriteMaterial:"sprite"};function x(g){return o.add(g),g===0?"uv":`uv${g}`}function M(g,w,T,C,D,V){let U=C.fog,z=D.geometry,q=g.isMeshStandardMaterial||g.isMeshLambertMaterial||g.isMeshPhongMaterial?C.environment:null,N=g.isMeshStandardMaterial||g.isMeshLambertMaterial&&!g.envMap||g.isMeshPhongMaterial&&!g.envMap,G=t.get(g.envMap||q,N),X=G&&G.mapping===Aa?G.image.height:null,K=p[g.type];g.precision!==null&&(d=n.getMaxPrecision(g.precision),d!==g.precision&&Zt("WebGLProgram.getParameters:",g.precision,"not supported, using",d,"instead."));let nt=z.morphAttributes.position||z.morphAttributes.normal||z.morphAttributes.color,tt=nt!==void 0?nt.length:0,lt=0;z.morphAttributes.position!==void 0&&(lt=1),z.morphAttributes.normal!==void 0&&(lt=2),z.morphAttributes.color!==void 0&&(lt=3);let zt,Lt,gt,J;if(K){let mt=Pi[K];zt=mt.vertexShader,Lt=mt.fragmentShader}else{zt=g.vertexShader,Lt=g.fragmentShader;let mt=l.getVertexShaderStage(g),vt=l.getFragmentShaderStage(g);l.update(g,mt,vt),gt=mt.id,J=vt.id}let et=i.getRenderTarget(),pt=i.state.buffers.depth.getReversed(),At=D.isInstancedMesh===!0,Mt=D.isBatchedMesh===!0,qt=!!g.map,ve=!!g.matcap,Jt=!!G,te=!!g.aoMap,ne=!!g.lightMap,jt=!!g.bumpMap&&g.wireframe===!1,xe=!!g.normalMap,ze=!!g.displacementMap,Ie=!!g.emissiveMap,pe=!!g.metalnessMap,_e=!!g.roughnessMap,Y=g.anisotropy>0,Xe=g.clearcoat>0,ye=g.dispersion>0,L=g.retroreflectivity>0,y=g.iridescence>0,$=g.sheen>0,Q=g.transmission>0,it=Y&&!!g.anisotropyMap,xt=Xe&&!!g.clearcoatMap,wt=Xe&&!!g.clearcoatNormalMap,rt=Xe&&!!g.clearcoatRoughnessMap,ot=y&&!!g.iridescenceMap,St=y&&!!g.iridescenceThicknessMap,Bt=$&&!!g.sheenColorMap,Pt=$&&!!g.sheenRoughnessMap,Et=!!g.specularMap,Ht=!!g.specularColorMap,Vt=!!g.specularIntensityMap,Wt=Q&&!!g.transmissionMap,W=Q&&!!g.thicknessMap,Rt=!!g.gradientMap,ht=!!g.alphaMap,Tt=g.alphaTest>0,It=!!g.alphaHash,B=!!g.extensions,at=ui;g.toneMapped&&(et===null||et.isXRRenderTarget===!0)&&(at=i.toneMapping);let ut={shaderID:K,shaderType:g.type,shaderName:g.name,vertexShader:zt,fragmentShader:Lt,defines:g.defines,customVertexShaderID:gt,customFragmentShaderID:J,isRawShaderMaterial:g.isRawShaderMaterial===!0,glslVersion:g.glslVersion,precision:d,batching:Mt,batchingColor:Mt&&D._colorsTexture!==null,instancing:At,instancingColor:At&&D.instanceColor!==null,instancingMorph:At&&D.morphTexture!==null,outputColorSpace:et===null?i.outputColorSpace:et.isXRRenderTarget===!0?et.texture.colorSpace:me.workingColorSpace,alphaToCoverage:!!g.alphaToCoverage,map:qt,matcap:ve,envMap:Jt,envMapMode:Jt&&G.mapping,envMapCubeUVHeight:X,aoMap:te,lightMap:ne,bumpMap:jt,normalMap:xe,displacementMap:ze,emissiveMap:Ie,normalMapObjectSpace:xe&&g.normalMapType===td,normalMapTangentSpace:xe&&g.normalMapType===Dl,packedNormalMap:xe&&g.normalMapType===Dl&&o_(g.normalMap.format),metalnessMap:pe,roughnessMap:_e,anisotropy:Y,anisotropyMap:it,clearcoat:Xe,clearcoatMap:xt,clearcoatNormalMap:wt,clearcoatRoughnessMap:rt,dispersion:ye,retroreflection:L,iridescence:y,iridescenceMap:ot,iridescenceThicknessMap:St,sheen:$,sheenColorMap:Bt,sheenRoughnessMap:Pt,specularMap:Et,specularColorMap:Ht,specularIntensityMap:Vt,transmission:Q,transmissionMap:Wt,thicknessMap:W,gradientMap:Rt,opaque:g.transparent===!1&&g.blending===Nr&&g.alphaToCoverage===!1,alphaMap:ht,alphaTest:Tt,alphaHash:It,combine:g.combine,mapUv:qt&&x(g.map.channel),aoMapUv:te&&x(g.aoMap.channel),lightMapUv:ne&&x(g.lightMap.channel),bumpMapUv:jt&&x(g.bumpMap.channel),normalMapUv:xe&&x(g.normalMap.channel),displacementMapUv:ze&&x(g.displacementMap.channel),emissiveMapUv:Ie&&x(g.emissiveMap.channel),metalnessMapUv:pe&&x(g.metalnessMap.channel),roughnessMapUv:_e&&x(g.roughnessMap.channel),anisotropyMapUv:it&&x(g.anisotropyMap.channel),clearcoatMapUv:xt&&x(g.clearcoatMap.channel),clearcoatNormalMapUv:wt&&x(g.clearcoatNormalMap.channel),clearcoatRoughnessMapUv:rt&&x(g.clearcoatRoughnessMap.channel),iridescenceMapUv:ot&&x(g.iridescenceMap.channel),iridescenceThicknessMapUv:St&&x(g.iridescenceThicknessMap.channel),sheenColorMapUv:Bt&&x(g.sheenColorMap.channel),sheenRoughnessMapUv:Pt&&x(g.sheenRoughnessMap.channel),specularMapUv:Et&&x(g.specularMap.channel),specularColorMapUv:Ht&&x(g.specularColorMap.channel),specularIntensityMapUv:Vt&&x(g.specularIntensityMap.channel),transmissionMapUv:Wt&&x(g.transmissionMap.channel),thicknessMapUv:W&&x(g.thicknessMap.channel),alphaMapUv:ht&&x(g.alphaMap.channel),vertexTangents:!!z.attributes.tangent&&(xe||Y),vertexNormals:!!z.attributes.normal,vertexColors:g.vertexColors,vertexAlphas:g.vertexColors===!0&&!!z.attributes.color&&z.attributes.color.itemSize===4,pointsUvs:D.isPoints===!0&&!!z.attributes.uv&&(qt||ht),fog:!!U,useFog:g.fog===!0,fogExp2:!!U&&U.isFogExp2,flatShading:g.wireframe===!1&&(g.flatShading===!0||z.attributes.normal===void 0&&xe===!1&&(g.isMeshLambertMaterial||g.isMeshPhongMaterial||g.isMeshStandardMaterial||g.isMeshPhysicalMaterial)),sizeAttenuation:g.sizeAttenuation===!0,logarithmicDepthBuffer:f,reversedDepthBuffer:pt,skinning:D.isSkinnedMesh===!0,hasPositionAttribute:z.attributes.position!==void 0,morphTargets:z.morphAttributes.position!==void 0,morphNormals:z.morphAttributes.normal!==void 0,morphColors:z.morphAttributes.color!==void 0,morphTargetsCount:tt,morphTextureStride:lt,numSunLights:w.sun.length,numDirLights:w.directional.length,numPointLights:w.point.length,numSpotLights:w.spot.length,numSpotLightMaps:w.spotLightMap.length,numRectAreaLights:w.rectArea.length,numHemiLights:w.hemi.length,numSunLightShadows:w.sunShadowMap.length,numDirLightShadows:w.directionalShadowMap.length,numPointLightShadows:w.pointShadowMap.length,numSpotLightShadows:w.spotShadowMap.length,numSpotLightShadowsWithMaps:w.numSpotLightShadowsWithMaps,numLightProbes:w.numLightProbes,numLightProbeGrids:V.length,numClippingPlanes:r.numPlanes,numClipIntersection:r.numIntersection,dithering:g.dithering,shadowMapEnabled:i.shadowMap.enabled&&T.length>0,shadowMapType:i.shadowMap.type,toneMapping:at,decodeVideoTexture:qt&&g.map.isVideoTexture===!0&&me.getTransfer(g.map.colorSpace)===Ae,decodeVideoTextureEmissive:Ie&&g.emissiveMap.isVideoTexture===!0&&me.getTransfer(g.emissiveMap.colorSpace)===Ae,premultipliedAlpha:g.premultipliedAlpha,doubleSided:g.side===Ai,flipSided:g.side===Tn,useDepthPacking:g.depthPacking>=0,depthPacking:g.depthPacking||0,index0AttributeName:g.index0AttributeName,extensionClipCullDistance:B&&g.extensions.clipCullDistance===!0&&e.has("WEBGL_clip_cull_distance"),extensionMultiDraw:(B&&g.extensions.multiDraw===!0||Mt)&&e.has("WEBGL_multi_draw"),rendererExtensionParallelShaderCompile:e.has("KHR_parallel_shader_compile"),customProgramCacheKey:g.customProgramCacheKey()};return ut.vertexUv1s=o.has(1),ut.vertexUv2s=o.has(2),ut.vertexUv3s=o.has(3),o.clear(),ut}function m(g){let w=[];if(g.shaderID?w.push(g.shaderID):(w.push(g.customVertexShaderID),w.push(g.customFragmentShaderID)),g.defines!==void 0)for(let T in g.defines)w.push(T),w.push(g.defines[T]);return g.isRawShaderMaterial===!1&&(u(w,g),b(w,g),w.push(i.outputColorSpace)),w.push(g.customProgramCacheKey),w.join()}function u(g,w){g.push(w.precision),g.push(w.outputColorSpace),g.push(w.envMapMode),g.push(w.envMapCubeUVHeight),g.push(w.mapUv),g.push(w.alphaMapUv),g.push(w.lightMapUv),g.push(w.aoMapUv),g.push(w.bumpMapUv),g.push(w.normalMapUv),g.push(w.displacementMapUv),g.push(w.emissiveMapUv),g.push(w.metalnessMapUv),g.push(w.roughnessMapUv),g.push(w.anisotropyMapUv),g.push(w.clearcoatMapUv),g.push(w.clearcoatNormalMapUv),g.push(w.clearcoatRoughnessMapUv),g.push(w.iridescenceMapUv),g.push(w.iridescenceThicknessMapUv),g.push(w.sheenColorMapUv),g.push(w.sheenRoughnessMapUv),g.push(w.specularMapUv),g.push(w.specularColorMapUv),g.push(w.specularIntensityMapUv),g.push(w.transmissionMapUv),g.push(w.thicknessMapUv),g.push(w.combine),g.push(w.fogExp2),g.push(w.sizeAttenuation),g.push(w.morphTargetsCount),g.push(w.morphAttributeCount),g.push(w.numSunLights),g.push(w.numDirLights),g.push(w.numPointLights),g.push(w.numSpotLights),g.push(w.numSpotLightMaps),g.push(w.numHemiLights),g.push(w.numRectAreaLights),g.push(w.numSunLightShadows),g.push(w.numDirLightShadows),g.push(w.numPointLightShadows),g.push(w.numSpotLightShadows),g.push(w.numSpotLightShadowsWithMaps),g.push(w.numLightProbes),g.push(w.shadowMapType),g.push(w.toneMapping),g.push(w.numClippingPlanes),g.push(w.numClipIntersection),g.push(w.depthPacking)}function b(g,w){a.disableAll(),w.instancing&&a.enable(0),w.instancingColor&&a.enable(1),w.instancingMorph&&a.enable(2),w.matcap&&a.enable(3),w.envMap&&a.enable(4),w.normalMapObjectSpace&&a.enable(5),w.normalMapTangentSpace&&a.enable(6),w.clearcoat&&a.enable(7),w.iridescence&&a.enable(8),w.alphaTest&&a.enable(9),w.vertexColors&&a.enable(10),w.vertexAlphas&&a.enable(11),w.vertexUv1s&&a.enable(12),w.vertexUv2s&&a.enable(13),w.vertexUv3s&&a.enable(14),w.vertexTangents&&a.enable(15),w.anisotropy&&a.enable(16),w.alphaHash&&a.enable(17),w.batching&&a.enable(18),w.dispersion&&a.enable(19),w.retroreflection&&a.enable(24),w.batchingColor&&a.enable(20),w.gradientMap&&a.enable(21),w.packedNormalMap&&a.enable(22),w.vertexNormals&&a.enable(23),g.push(a.mask),a.disableAll(),w.fog&&a.enable(0),w.useFog&&a.enable(1),w.flatShading&&a.enable(2),w.logarithmicDepthBuffer&&a.enable(3),w.reversedDepthBuffer&&a.enable(4),w.skinning&&a.enable(5),w.morphTargets&&a.enable(6),w.morphNormals&&a.enable(7),w.morphColors&&a.enable(8),w.premultipliedAlpha&&a.enable(9),w.shadowMapEnabled&&a.enable(10),w.doubleSided&&a.enable(11),w.flipSided&&a.enable(12),w.useDepthPacking&&a.enable(13),w.dithering&&a.enable(14),w.transmission&&a.enable(15),w.sheen&&a.enable(16),w.opaque&&a.enable(17),w.pointsUvs&&a.enable(18),w.decodeVideoTexture&&a.enable(19),w.decodeVideoTextureEmissive&&a.enable(20),w.alphaToCoverage&&a.enable(21),w.numLightProbeGrids>0&&a.enable(22),w.hasPositionAttribute&&a.enable(23),g.push(a.mask)}function A(g){let w=p[g.type],T;if(w){let C=Pi[w];T=pd.clone(C.uniforms)}else T=g.uniforms;return T}function v(g,w){let T=h.get(w);return T!==void 0?++T.usedTimes:(T=new r_(i,w,g,s),c.push(T),h.set(w,T)),T}function S(g){if(--g.usedTimes===0){let w=c.indexOf(g);c[w]=c[c.length-1],c.pop(),h.delete(g.cacheKey),g.destroy()}}function E(g){l.remove(g)}function R(){l.dispose()}return{getParameters:M,getProgramCacheKey:m,getUniforms:A,acquireProgram:v,releaseProgram:S,releaseShaderCache:E,programs:c,dispose:R}}function c_(){let i=new WeakMap;function t(a){return i.has(a)}function e(a){let l=i.get(a);return l===void 0&&(l={},i.set(a,l)),l}function n(a){i.delete(a)}function s(a,l,o){i.get(a)[l]=o}function r(){i=new WeakMap}return{has:t,get:e,remove:n,update:s,dispose:r}}function h_(i,t){return i.groupOrder!==t.groupOrder?i.groupOrder-t.groupOrder:i.renderOrder!==t.renderOrder?i.renderOrder-t.renderOrder:i.material.id!==t.material.id?i.material.id-t.material.id:i.materialVariant!==t.materialVariant?i.materialVariant-t.materialVariant:i.z!==t.z?i.z-t.z:i.id-t.id}function Dd(i,t){return i.groupOrder!==t.groupOrder?i.groupOrder-t.groupOrder:i.renderOrder!==t.renderOrder?i.renderOrder-t.renderOrder:i.z!==t.z?t.z-i.z:i.id-t.id}function Nd(){let i=[],t=0,e=[],n=[],s=[];function r(){t=0,e.length=0,n.length=0,s.length=0}function a(d){let p=0;return d.isInstancedMesh&&(p+=2),d.isSkinnedMesh&&(p+=1),p}function l(d,p,x,M,m,u){let b=i[t];return b===void 0?(b={id:d.id,object:d,geometry:p,material:x,materialVariant:a(d),groupOrder:M,renderOrder:d.renderOrder,z:m,group:u},i[t]=b):(b.id=d.id,b.object=d,b.geometry=p,b.material=x,b.materialVariant=a(d),b.groupOrder=M,b.renderOrder=d.renderOrder,b.z=m,b.group=u),t++,b}function o(d,p,x,M,m,u,b){b.reversedDepth===!0&&(m=-m);let A=l(d,p,x,M,m,u);x.transmission>0?n.push(A):x.transparent===!0?s.push(A):e.push(A)}function c(d,p,x,M,m,u){let b=l(d,p,x,M,m,u);x.transmission>0?n.unshift(b):x.transparent===!0?s.unshift(b):e.unshift(b)}function h(d,p){e.length>1&&e.sort(d||h_),n.length>1&&n.sort(p||Dd),s.length>1&&s.sort(p||Dd)}function f(){for(let d=t,p=i.length;d<p;d++){let x=i[d];if(x.id===null)break;x.id=null,x.object=null,x.geometry=null,x.material=null,x.group=null}}return{opaque:e,transmissive:n,transparent:s,init:r,push:o,unshift:c,finish:f,sort:h}}function u_(){let i=new WeakMap;function t(n,s){let r=i.get(n),a;return r===void 0?(a=new Nd,i.set(n,[a])):s>=r.length?(a=new Nd,r.push(a)):a=r[s],a}function e(){i=new WeakMap}return{get:t,dispose:e}}function d_(){let i={};return{get:function(t){if(i[t.id]!==void 0)return i[t.id];let e;switch(t.type){case"SunLight":case"DirectionalLight":e={direction:new F,color:new $t};break;case"SpotLight":e={position:new F,direction:new F,color:new $t,distance:0,coneCos:0,penumbraCos:0,decay:0};break;case"PointLight":e={position:new F,color:new $t,distance:0,decay:0};break;case"HemisphereLight":e={direction:new F,skyColor:new $t,groundColor:new $t};break;case"RectAreaLight":e={color:new $t,position:new F,halfWidth:new F,halfHeight:new F};break}return i[t.id]=e,e}}}function f_(){let i={};return{get:function(t){if(i[t.id]!==void 0)return i[t.id];let e;switch(t.type){case"SunLight":case"DirectionalLight":e={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new Xt};break;case"SpotLight":e={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new Xt};break;case"PointLight":e={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new Xt,shadowCameraNear:1,shadowCameraFar:1e3};break}return i[t.id]=e,e}}}var p_=0;function m_(i,t){return(t.castShadow?2:0)-(i.castShadow?2:0)+(t.map?1:0)-(i.map?1:0)}function g_(i){let t=new d_,e=f_(),n={version:0,hash:{sunLength:-1,directionalLength:-1,pointLength:-1,spotLength:-1,rectAreaLength:-1,hemiLength:-1,numSunShadows:-1,numDirectionalShadows:-1,numPointShadows:-1,numSpotShadows:-1,numSpotMaps:-1,numLightProbes:-1},ambient:[0,0,0],probe:[],sun:[],sunShadow:[],sunShadowMap:[],sunShadowMatrix:[],sunShadowCascade:[],directional:[],directionalShadow:[],directionalShadowMap:[],directionalShadowMatrix:[],spot:[],spotLightMap:[],spotShadow:[],spotShadowMap:[],spotLightMatrix:[],rectArea:[],rectAreaLTC1:null,rectAreaLTC2:null,point:[],pointShadow:[],pointShadowMap:[],pointShadowMatrix:[],hemi:[],numSpotLightShadowsWithMaps:0,numLightProbes:0};for(let c=0;c<9;c++)n.probe.push(new F);let s=new F,r=new ge,a=new ge;function l(c){let h=0,f=0,d=0;for(let D=0;D<9;D++)n.probe[D].set(0,0,0);let p=0,x=0,M=0,m=0,u=0,b=0,A=0,v=0,S=0,E=0,R=0,g=0,w=0,T=0;c.sort(m_);for(let D=0,V=c.length;D<V;D++){let U=c[D],z=U.color,q=U.intensity,N=U.distance,G=null;if(U.shadow&&U.shadow.map&&(U.shadow.map.texture.format===Es?G=U.shadow.map.texture:G=U.shadow.map.depthTexture||U.shadow.map.texture),U.isAmbientLight)h+=z.r*q,f+=z.g*q,d+=z.b*q;else if(U.isLightProbe){for(let X=0;X<9;X++)n.probe[X].addScaledVector(U.sh.coefficients[X],q);T++}else if(U.isSunLight){let X=t.get(U);if(X.color.copy(U.color).multiplyScalar(U.intensity),U.castShadow){let K=U.shadow,nt=e.get(U);nt.shadowIntensity=K.intensity,nt.shadowBias=K.bias,nt.shadowNormalBias=K.normalBias,nt.shadowRadius=K.radius,nt.shadowMapSize.copy(K.mapSize).multiply(K.getFrameExtents()),n.sunShadow[x]=nt,n.sunShadowMap[x]=G;let tt=K.getViewportCount();for(let lt=0;lt<tt;lt++)n.sunShadowMatrix[M+lt]=K.getMatrix(lt),n.sunShadowCascade[M+lt]=K._cascadeData[lt];M+=tt,x++}n.sun[p]=X,p++}else if(U.isDirectionalLight){let X=t.get(U);if(X.color.copy(U.color).multiplyScalar(U.intensity),U.castShadow){let K=U.shadow,nt=e.get(U);nt.shadowIntensity=K.intensity,nt.shadowBias=K.bias,nt.shadowNormalBias=K.normalBias,nt.shadowRadius=K.radius,nt.shadowMapSize=K.mapSize,n.directionalShadow[m]=nt,n.directionalShadowMap[m]=G,n.directionalShadowMatrix[m]=U.shadow.matrix,S++}n.directional[m]=X,m++}else if(U.isSpotLight){let X=t.get(U);X.position.setFromMatrixPosition(U.matrixWorld),X.color.copy(z).multiplyScalar(q),X.distance=N,X.coneCos=Math.cos(U.angle),X.penumbraCos=Math.cos(U.angle*(1-U.penumbra)),X.decay=U.decay,n.spot[b]=X;let K=U.shadow;if(U.map&&(n.spotLightMap[g]=U.map,g++,K.updateMatrices(U),U.castShadow&&w++),n.spotLightMatrix[b]=K.matrix,U.castShadow){let nt=e.get(U);nt.shadowIntensity=K.intensity,nt.shadowBias=K.bias,nt.shadowNormalBias=K.normalBias,nt.shadowRadius=K.radius,nt.shadowMapSize=K.mapSize,n.spotShadow[b]=nt,n.spotShadowMap[b]=G,R++}b++}else if(U.isRectAreaLight){let X=t.get(U);X.color.copy(z).multiplyScalar(q),X.halfWidth.set(U.width*.5,0,0),X.halfHeight.set(0,U.height*.5,0),n.rectArea[A]=X,A++}else if(U.isPointLight){let X=t.get(U);if(X.color.copy(U.color).multiplyScalar(U.intensity),X.distance=U.distance,X.decay=U.decay,U.castShadow){let K=U.shadow,nt=e.get(U);nt.shadowIntensity=K.intensity,nt.shadowBias=K.bias,nt.shadowNormalBias=K.normalBias,nt.shadowRadius=K.radius,nt.shadowMapSize=K.mapSize,nt.shadowCameraNear=K.camera.near,nt.shadowCameraFar=K.camera.far,n.pointShadow[u]=nt,n.pointShadowMap[u]=G,n.pointShadowMatrix[u]=U.shadow.matrix,E++}n.point[u]=X,u++}else if(U.isHemisphereLight){let X=t.get(U);X.skyColor.copy(U.color).multiplyScalar(q),X.groundColor.copy(U.groundColor).multiplyScalar(q),n.hemi[v]=X,v++}}A>0&&(i.has("OES_texture_float_linear")===!0?(n.rectAreaLTC1=Dt.LTC_FLOAT_1,n.rectAreaLTC2=Dt.LTC_FLOAT_2):(n.rectAreaLTC1=Dt.LTC_HALF_1,n.rectAreaLTC2=Dt.LTC_HALF_2)),n.ambient[0]=h,n.ambient[1]=f,n.ambient[2]=d;let C=n.hash;(C.sunLength!==p||C.directionalLength!==m||C.pointLength!==u||C.spotLength!==b||C.rectAreaLength!==A||C.hemiLength!==v||C.numSunShadows!==x||C.numDirectionalShadows!==S||C.numPointShadows!==E||C.numSpotShadows!==R||C.numSpotMaps!==g||C.numLightProbes!==T)&&(n.sun.length=p,n.directional.length=m,n.spot.length=b,n.rectArea.length=A,n.point.length=u,n.hemi.length=v,n.sunShadow.length=x,n.sunShadowMap.length=x,n.sunShadowMatrix.length=M,n.sunShadowCascade.length=M,n.directionalShadow.length=S,n.directionalShadowMap.length=S,n.directionalShadowMatrix.length=S,n.pointShadow.length=E,n.pointShadowMap.length=E,n.pointShadowMatrix.length=E,n.spotShadow.length=R,n.spotShadowMap.length=R,n.spotLightMatrix.length=R+g-w,n.spotLightMap.length=g,n.numSpotLightShadowsWithMaps=w,n.numLightProbes=T,C.sunLength=p,C.directionalLength=m,C.pointLength=u,C.spotLength=b,C.rectAreaLength=A,C.hemiLength=v,C.numSunShadows=x,C.numDirectionalShadows=S,C.numPointShadows=E,C.numSpotShadows=R,C.numSpotMaps=g,C.numLightProbes=T,n.version=p_++)}function o(c,h){let f=0,d=0,p=0,x=0,M=0,m=0,u=h.matrixWorldInverse;for(let b=0,A=c.length;b<A;b++){let v=c[b];if(v.isSunLight){let S=n.sun[f];S.direction.setFromMatrixPosition(v.matrixWorld),S.direction.transformDirection(u),f++}else if(v.isDirectionalLight){let S=n.directional[d];S.direction.setFromMatrixPosition(v.matrixWorld),s.setFromMatrixPosition(v.target.matrixWorld),S.direction.sub(s),S.direction.transformDirection(u),d++}else if(v.isSpotLight){let S=n.spot[x];S.position.setFromMatrixPosition(v.matrixWorld),S.position.applyMatrix4(u),S.direction.setFromMatrixPosition(v.matrixWorld),s.setFromMatrixPosition(v.target.matrixWorld),S.direction.sub(s),S.direction.transformDirection(u),x++}else if(v.isRectAreaLight){let S=n.rectArea[M];S.position.setFromMatrixPosition(v.matrixWorld),S.position.applyMatrix4(u),a.identity(),r.copy(v.matrixWorld),r.premultiply(u),a.extractRotation(r),S.halfWidth.set(v.width*.5,0,0),S.halfHeight.set(0,v.height*.5,0),S.halfWidth.applyMatrix4(a),S.halfHeight.applyMatrix4(a),M++}else if(v.isPointLight){let S=n.point[p];S.position.setFromMatrixPosition(v.matrixWorld),S.position.applyMatrix4(u),p++}else if(v.isHemisphereLight){let S=n.hemi[m];S.direction.setFromMatrixPosition(v.matrixWorld),S.direction.transformDirection(u),m++}}}return{setup:l,setupView:o,state:n}}function Ud(i){let t=new g_(i),e=[],n=[],s=[];function r(d){f.camera=d,e.length=0,n.length=0,s.length=0}function a(d){e.push(d)}function l(d){n.push(d)}function o(d){s.push(d)}function c(){t.setup(e)}function h(d){t.setupView(e,d)}let f={lightsArray:e,shadowsArray:n,lightProbeGridArray:s,camera:null,lights:t,transmissionRenderTarget:{},textureUnits:0};return{init:r,state:f,setupLights:c,setupLightsView:h,pushLight:a,pushShadow:l,pushLightProbeGrid:o}}function x_(i){let t=new WeakMap;function e(s,r=0){let a=t.get(s),l;return a===void 0?(l=new Ud(i),t.set(s,[l])):r>=a.length?(l=new Ud(i),a.push(l)):l=a[r],l}function n(){t=new WeakMap}return{get:e,dispose:n}}var __=`void main() {
	gl_Position = vec4( position, 1.0 );
}`,y_=`uniform sampler2D shadow_pass;
uniform vec2 resolution;
uniform float radius;
void main() {
	const float samples = float( VSM_SAMPLES );
	float mean = 0.0;
	float squared_mean = 0.0;
	float uvStride = samples <= 1.0 ? 0.0 : 2.0 / ( samples - 1.0 );
	float uvStart = samples <= 1.0 ? 0.0 : - 1.0;
	for ( float i = 0.0; i < samples; i ++ ) {
		float uvOffset = uvStart + i * uvStride;
		#ifdef HORIZONTAL_PASS
			vec2 distribution = texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( uvOffset, 0.0 ) * radius ) / resolution ).rg;
			mean += distribution.x;
			squared_mean += distribution.y * distribution.y + distribution.x * distribution.x;
		#else
			float depth = texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( 0.0, uvOffset ) * radius ) / resolution ).r;
			mean += depth;
			squared_mean += depth * depth;
		#endif
	}
	mean = mean / samples;
	squared_mean = squared_mean / samples;
	float std_dev = sqrt( max( 0.0, squared_mean - mean * mean ) );
	gl_FragColor = vec4( mean, std_dev, 0.0, 1.0 );
}`,v_=[new F(1,0,0),new F(-1,0,0),new F(0,1,0),new F(0,-1,0),new F(0,0,1),new F(0,0,-1)],b_=[new F(0,-1,0),new F(0,-1,0),new F(0,0,1),new F(0,0,-1),new F(0,-1,0),new F(0,-1,0)],Fd=new ge,Ua=new F,Sh=new F;function M_(i,t,e){let n=new Pr,s=new Xt,r=new Xt,a=new ke,l=new zo,o=new Do,c={},h=e.maxTextureSize,f={[vs]:Tn,[Tn]:vs,[Ai]:Ai},d=new Vn({defines:{VSM_SAMPLES:8},uniforms:{shadow_pass:{value:null},resolution:{value:new Xt},radius:{value:4}},vertexShader:__,fragmentShader:y_}),p=d.clone();p.defines.HORIZONTAL_PASS=1;let x=new je;x.setAttribute("position",new pn(new Float32Array([-1,-1,.5,3,-1,.5,-1,3,.5]),3));let M=new kt(x,d),m=this;this.enabled=!1,this.autoUpdate=!0,this.needsUpdate=!1,this.type=Zi;let u=this.type;this.render=function(E,R,g){if(m.enabled===!1||m.autoUpdate===!1&&m.needsUpdate===!1||E.length===0)return;this.type===Iu&&(Zt("WebGLShadowMap: PCFSoftShadowMap has been removed. Using PCFShadowMap instead."),this.type=Zi);let w=i.getRenderTarget(),T=i.getActiveCubeFace(),C=i.getActiveMipmapLevel(),D=i.state;D.setBlending(Ri),D.buffers.depth.getReversed()===!0?D.buffers.color.setClear(0,0,0,0):D.buffers.color.setClear(1,1,1,1),D.buffers.depth.setTest(!0),D.setScissorTest(!1);let V=u!==this.type;V&&R.traverse(function(U){U.material&&(Array.isArray(U.material)?U.material.forEach(z=>z.needsUpdate=!0):U.material.needsUpdate=!0)});for(let U=0,z=E.length;U<z;U++){let q=E[U],N=q.shadow;if(N===void 0){Zt("WebGLShadowMap:",q,"has no shadow.");continue}if(N.autoUpdate===!1&&N.needsUpdate===!1)continue;s.copy(N.mapSize);let G=N.getFrameExtents();s.multiply(G),r.copy(N.mapSize),(s.x>h||s.y>h)&&(s.x>h&&(r.x=Math.floor(h/G.x),s.x=r.x*G.x,N.mapSize.x=r.x),s.y>h&&(r.y=Math.floor(h/G.y),s.y=r.y*G.y,N.mapSize.y=r.y));let X=i.state.buffers.depth.getReversed();if(N.camera._reversedDepth=X,N.map===null||V===!0){if(N.map!==null&&(N.map.depthTexture!==null&&(N.map.depthTexture.dispose(),N.map.depthTexture=null),N.map.dispose()),this.type===Dr){if(q.isPointLight){Zt("WebGLShadowMap: VSM shadow maps are not supported for PointLights. Use PCF or BasicShadowMap instead.");continue}N.map=new In(s.x,s.y,{format:Es,type:fi,minFilter:mn,magFilter:mn,generateMipmaps:!1}),N.map.texture.name=q.name+".shadowMap",N.map.depthTexture=new ps(s.x,s.y,Zn),N.map.depthTexture.name=q.name+".shadowMapDepth",N.map.depthTexture.format=Ei,N.map.depthTexture.compareFunction=null,N.map.depthTexture.minFilter=an,N.map.depthTexture.magFilter=an}else q.isPointLight?(N.map=new kl(s.x),N.map.depthTexture=new Po(s.x,di)):(N.map=new In(s.x,s.y),N.map.depthTexture=new ps(s.x,s.y,di)),N.map.depthTexture.name=q.name+".shadowMap",N.map.depthTexture.format=Ei,this.type===Zi?(N.map.depthTexture.compareFunction=X?Ul:Nl,N.map.depthTexture.minFilter=mn,N.map.depthTexture.magFilter=mn):(N.map.depthTexture.compareFunction=null,N.map.depthTexture.minFilter=an,N.map.depthTexture.magFilter=an);N.camera.updateProjectionMatrix()}N.map.isWebGLCubeRenderTarget!==!0&&(N.map.width!==s.x||N.map.height!==s.y)&&N.map.setSize(s.x,s.y);let K=N.map.isWebGLCubeRenderTarget?6:N.getViewportCount();q.isPointLight!==!0&&N.updateMatrices(q,g);for(let nt=0;nt<K;nt++){let tt=N.getCamera(nt);if(q.isPointLight){let lt=N.camera,zt=N.matrix,Lt=q.distance||lt.far;Lt!==lt.far&&(lt.far=Lt,lt.updateProjectionMatrix()),Ua.setFromMatrixPosition(q.matrixWorld),lt.position.copy(Ua),Sh.copy(lt.position),Sh.add(v_[nt]),lt.up.copy(b_[nt]),lt.lookAt(Sh),lt.updateMatrixWorld(),zt.makeTranslation(-Ua.x,-Ua.y,-Ua.z),Fd.multiplyMatrices(lt.projectionMatrix,lt.matrixWorldInverse),N._frustum.setFromProjectionMatrix(Fd,lt.coordinateSystem,lt.reversedDepth)}if(N.map.isWebGLCubeRenderTarget)i.setRenderTarget(N.map,nt),i.clear();else{nt===0&&(i.setRenderTarget(N.map),i.clear());let lt=N.getViewport(nt);a.set(r.x*lt.x,r.y*lt.y,r.x*lt.z,r.y*lt.w),D.viewport(a)}n=N.getFrustum(nt),v(R,g,tt,q,this.type)}N.isPointLightShadow!==!0&&this.type===Dr&&b(N,g),N.needsUpdate=!1}u=this.type,m.needsUpdate=!1,i.setRenderTarget(w,T,C)};function b(E,R){let g=t.update(M);d.defines.VSM_SAMPLES!==E.blurSamples&&(d.defines.VSM_SAMPLES=E.blurSamples,p.defines.VSM_SAMPLES=E.blurSamples,d.needsUpdate=!0,p.needsUpdate=!0),E.mapPass===null?E.mapPass=new In(s.x,s.y,{format:Es,type:fi}):(E.mapPass.width!==E.map.width||E.mapPass.height!==E.map.height)&&E.mapPass.setSize(E.map.width,E.map.height),d.uniforms.shadow_pass.value=E.map.depthTexture,d.uniforms.resolution.value.set(E.map.width,E.map.height),d.uniforms.radius.value=E.radius,i.setRenderTarget(E.mapPass),i.clear(),i.renderBufferDirect(R,null,g,d,M,null),p.uniforms.shadow_pass.value=E.mapPass.texture,p.uniforms.resolution.value.set(E.map.width,E.map.height),p.uniforms.radius.value=E.radius,i.setRenderTarget(E.map),i.clear(),i.renderBufferDirect(R,null,g,p,M,null)}function A(E,R,g,w){let T=null,C=g.isPointLight===!0?E.customDistanceMaterial:E.customDepthMaterial;if(C!==void 0)T=C;else if(T=g.isPointLight===!0?o:l,i.localClippingEnabled&&R.clipShadows===!0&&Array.isArray(R.clippingPlanes)&&R.clippingPlanes.length!==0||R.displacementMap&&R.displacementScale!==0||R.alphaMap&&R.alphaTest>0||R.map&&R.alphaTest>0||R.alphaToCoverage===!0){let D=T.uuid,V=R.uuid,U=c[D];U===void 0&&(U={},c[D]=U);let z=U[V];z===void 0&&(z=T.clone(),U[V]=z,R.addEventListener("dispose",S)),T=z}if(T.visible=R.visible,T.wireframe=R.wireframe,w===Dr?T.side=R.shadowSide!==null?R.shadowSide:R.side:T.side=R.shadowSide!==null?R.shadowSide:f[R.side],T.alphaMap=R.alphaMap,T.alphaTest=R.alphaToCoverage===!0?.5:R.alphaTest,T.map=R.map,T.clipShadows=R.clipShadows,T.clippingPlanes=R.clippingPlanes,T.clipIntersection=R.clipIntersection,T.displacementMap=R.displacementMap,T.displacementScale=R.displacementScale,T.displacementBias=R.displacementBias,T.wireframeLinewidth=R.wireframeLinewidth,T.linewidth=R.linewidth,g.isPointLight===!0&&T.isMeshDistanceMaterial===!0){let D=i.properties.get(T);D.light=g}return T}function v(E,R,g,w,T){if(E.visible===!1)return;if(E.layers.test(R.layers)&&(E.isMesh||E.isLine||E.isPoints)&&(E.castShadow||E.receiveShadow&&T===Dr)&&(!E.frustumCulled||E.intersectsFrustum(n))){E.modelViewMatrix.multiplyMatrices(g.matrixWorldInverse,E.matrixWorld);let V=t.update(E),U=E.material;if(Array.isArray(U)){let z=V.groups;for(let q=0,N=z.length;q<N;q++){let G=z[q],X=U[G.materialIndex];if(X&&X.visible){let K=A(E,X,w,T);E.onBeforeShadow(i,E,R,g,V,K,G),i.renderBufferDirect(g,null,V,K,E,G),E.onAfterShadow(i,E,R,g,V,K,G)}}}else if(U.visible){let z=A(E,U,w,T);E.onBeforeShadow(i,E,R,g,V,z,null),i.renderBufferDirect(g,null,V,z,E,null),E.onAfterShadow(i,E,R,g,V,z,null)}}let D=E.children;for(let V=0,U=D.length;V<U;V++)v(D[V],R,g,w,T)}function S(E){E.target.removeEventListener("dispose",S);for(let g in c){let w=c[g],T=E.target.uuid;T in w&&(w[T].dispose(),delete w[T])}}}function S_(i,t){function e(){let W=!1,Rt=new ke,ht=null,Tt=new ke(0,0,0,0);return{setMask:function(It){ht!==It&&!W&&(i.colorMask(It,It,It,It),ht=It)},setLocked:function(It){W=It},setClear:function(It,B,at,ut,mt){mt===!0&&(It*=ut,B*=ut,at*=ut),Rt.set(It,B,at,ut),Tt.equals(Rt)===!1&&(i.clearColor(It,B,at,ut),Tt.copy(Rt))},reset:function(){W=!1,ht=null,Tt.set(-1,0,0,0)}}}function n(){let W=!1,Rt=!1,ht=null,Tt=null,It=null;return{setReversed:function(B){if(Rt!==B){let at=t.get("EXT_clip_control");B?at.clipControlEXT(at.LOWER_LEFT_EXT,at.ZERO_TO_ONE_EXT):at.clipControlEXT(at.LOWER_LEFT_EXT,at.NEGATIVE_ONE_TO_ONE_EXT),Rt=B;let ut=It;It=null,this.setClear(ut)}},getReversed:function(){return Rt},setTest:function(B){B?et(i.DEPTH_TEST):pt(i.DEPTH_TEST)},setMask:function(B){ht!==B&&!W&&(i.depthMask(B),ht=B)},setFunc:function(B){if(Rt&&(B=dd[B]),Tt!==B){switch(B){case _o:i.depthFunc(i.NEVER);break;case yo:i.depthFunc(i.ALWAYS);break;case vo:i.depthFunc(i.LESS);break;case Mr:i.depthFunc(i.LEQUAL);break;case bo:i.depthFunc(i.EQUAL);break;case Mo:i.depthFunc(i.GEQUAL);break;case So:i.depthFunc(i.GREATER);break;case Eo:i.depthFunc(i.NOTEQUAL);break;default:i.depthFunc(i.LEQUAL)}Tt=B}},setLocked:function(B){W=B},setClear:function(B){It!==B&&(It=B,Rt&&(B=1-B),i.clearDepth(B))},reset:function(){W=!1,ht=null,Tt=null,It=null,Rt=!1}}}function s(){let W=!1,Rt=null,ht=null,Tt=null,It=null,B=null,at=null,ut=null,mt=null;return{setTest:function(vt){W||(vt?et(i.STENCIL_TEST):pt(i.STENCIL_TEST))},setMask:function(vt){Rt!==vt&&!W&&(i.stencilMask(vt),Rt=vt)},setFunc:function(vt,re,Ft){(ht!==vt||Tt!==re||It!==Ft)&&(i.stencilFunc(vt,re,Ft),ht=vt,Tt=re,It=Ft)},setOp:function(vt,re,Ft){(B!==vt||at!==re||ut!==Ft)&&(i.stencilOp(vt,re,Ft),B=vt,at=re,ut=Ft)},setLocked:function(vt){W=vt},setClear:function(vt){mt!==vt&&(i.clearStencil(vt),mt=vt)},reset:function(){W=!1,Rt=null,ht=null,Tt=null,It=null,B=null,at=null,ut=null,mt=null}}}let r=new e,a=new n,l=new s,o=new WeakMap,c=new WeakMap,h={},f={},d={},p=new WeakMap,x=[],M=null,m=!1,u=null,b=null,A=null,v=null,S=null,E=null,R=null,g=new $t(0,0,0),w=0,T=!1,C=null,D=null,V=null,U=null,z=null,q=i.getParameter(i.MAX_COMBINED_TEXTURE_IMAGE_UNITS),N=!1,G=0,X=i.getParameter(i.VERSION);X.indexOf("WebGL")!==-1?(G=parseFloat(/^WebGL (\d)/.exec(X)[1]),N=G>=1):X.indexOf("OpenGL ES")!==-1&&(G=parseFloat(/^OpenGL ES (\d)/.exec(X)[1]),N=G>=2);let K=null,nt={},tt=i.getParameter(i.SCISSOR_BOX),lt=i.getParameter(i.VIEWPORT),zt=new ke().fromArray(tt),Lt=new ke().fromArray(lt);function gt(W,Rt,ht,Tt){let It=new Uint8Array(4),B=i.createTexture();i.bindTexture(W,B),i.texParameteri(W,i.TEXTURE_MIN_FILTER,i.NEAREST),i.texParameteri(W,i.TEXTURE_MAG_FILTER,i.NEAREST);for(let at=0;at<ht;at++)W===i.TEXTURE_3D||W===i.TEXTURE_2D_ARRAY?i.texImage3D(Rt,0,i.RGBA,1,1,Tt,0,i.RGBA,i.UNSIGNED_BYTE,It):i.texImage2D(Rt+at,0,i.RGBA,1,1,0,i.RGBA,i.UNSIGNED_BYTE,It);return B}let J={};J[i.TEXTURE_2D]=gt(i.TEXTURE_2D,i.TEXTURE_2D,1),J[i.TEXTURE_CUBE_MAP]=gt(i.TEXTURE_CUBE_MAP,i.TEXTURE_CUBE_MAP_POSITIVE_X,6),J[i.TEXTURE_2D_ARRAY]=gt(i.TEXTURE_2D_ARRAY,i.TEXTURE_2D_ARRAY,1,1),J[i.TEXTURE_3D]=gt(i.TEXTURE_3D,i.TEXTURE_3D,1,1),r.setClear(0,0,0,1),a.setClear(1),l.setClear(0),et(i.DEPTH_TEST),a.setFunc(Mr),jt(!1),xe(kc),et(i.CULL_FACE),te(Ri);function et(W){h[W]!==!0&&(i.enable(W),h[W]=!0)}function pt(W){h[W]!==!1&&(i.disable(W),h[W]=!1)}function At(W,Rt){return d[W]!==Rt?(i.bindFramebuffer(W,Rt),d[W]=Rt,W===i.DRAW_FRAMEBUFFER&&(d[i.FRAMEBUFFER]=Rt),W===i.FRAMEBUFFER&&(d[i.DRAW_FRAMEBUFFER]=Rt),!0):!1}function Mt(W,Rt){let ht=x,Tt=!1;if(W){ht=p.get(Rt),ht===void 0&&(ht=[],p.set(Rt,ht));let It=W.textures;if(ht.length!==It.length||ht[0]!==i.COLOR_ATTACHMENT0){for(let B=0,at=It.length;B<at;B++)ht[B]=i.COLOR_ATTACHMENT0+B;ht.length=It.length,Tt=!0}}else ht[0]!==i.BACK&&(ht[0]=i.BACK,Tt=!0);Tt&&i.drawBuffers(ht)}function qt(W){return M!==W?(i.useProgram(W),M=W,!0):!1}let ve={[Xs]:i.FUNC_ADD,[zu]:i.FUNC_SUBTRACT,[Du]:i.FUNC_REVERSE_SUBTRACT};ve[Nu]=i.MIN,ve[Uu]=i.MAX;let Jt={[Fu]:i.ZERO,[Ou]:i.ONE,[Bu]:i.SRC_COLOR,[Wc]:i.SRC_ALPHA,[Xu]:i.SRC_ALPHA_SATURATE,[Gu]:i.DST_COLOR,[Hu]:i.DST_ALPHA,[ku]:i.ONE_MINUS_SRC_COLOR,[Xc]:i.ONE_MINUS_SRC_ALPHA,[Wu]:i.ONE_MINUS_DST_COLOR,[Vu]:i.ONE_MINUS_DST_ALPHA,[qu]:i.CONSTANT_COLOR,[Yu]:i.ONE_MINUS_CONSTANT_COLOR,[Zu]:i.CONSTANT_ALPHA,[$u]:i.ONE_MINUS_CONSTANT_ALPHA};function te(W,Rt,ht,Tt,It,B,at,ut,mt,vt){if(W===Ri){m===!0&&(pt(i.BLEND),m=!1);return}if(m===!1&&(et(i.BLEND),m=!0),W!==Lu){if(W!==u||vt!==T){if((b!==Xs||S!==Xs)&&(i.blendEquation(i.FUNC_ADD),b=Xs,S=Xs),vt)switch(W){case Nr:i.blendFuncSeparate(i.ONE,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case Hc:i.blendFunc(i.ONE,i.ONE);break;case Vc:i.blendFuncSeparate(i.ZERO,i.ONE_MINUS_SRC_COLOR,i.ZERO,i.ONE);break;case Gc:i.blendFuncSeparate(i.DST_COLOR,i.ONE_MINUS_SRC_ALPHA,i.ZERO,i.ONE);break;default:Kt("WebGLState: Invalid blending: ",W);break}else switch(W){case Nr:i.blendFuncSeparate(i.SRC_ALPHA,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case Hc:i.blendFuncSeparate(i.SRC_ALPHA,i.ONE,i.ONE,i.ONE);break;case Vc:Kt("WebGLState: SubtractiveBlending requires material.premultipliedAlpha = true");break;case Gc:Kt("WebGLState: MultiplyBlending requires material.premultipliedAlpha = true");break;default:Kt("WebGLState: Invalid blending: ",W);break}A=null,v=null,E=null,R=null,g.set(0,0,0),w=0,u=W,T=vt}return}It=It||Rt,B=B||ht,at=at||Tt,(Rt!==b||It!==S)&&(i.blendEquationSeparate(ve[Rt],ve[It]),b=Rt,S=It),(ht!==A||Tt!==v||B!==E||at!==R)&&(i.blendFuncSeparate(Jt[ht],Jt[Tt],Jt[B],Jt[at]),A=ht,v=Tt,E=B,R=at),(ut.equals(g)===!1||mt!==w)&&(i.blendColor(ut.r,ut.g,ut.b,mt),g.copy(ut),w=mt),u=W,T=!1}function ne(W,Rt){W.side===Ai?pt(i.CULL_FACE):et(i.CULL_FACE);let ht=W.side===Tn;Rt&&(ht=!ht),jt(ht),W.blending===Nr&&W.transparent===!1?te(Ri):te(W.blending,W.blendEquation,W.blendSrc,W.blendDst,W.blendEquationAlpha,W.blendSrcAlpha,W.blendDstAlpha,W.blendColor,W.blendAlpha,W.premultipliedAlpha),a.setFunc(W.depthFunc),a.setTest(W.depthTest),a.setMask(W.depthWrite),r.setMask(W.colorWrite);let Tt=W.stencilWrite;l.setTest(Tt),Tt&&(l.setMask(W.stencilWriteMask),l.setFunc(W.stencilFunc,W.stencilRef,W.stencilFuncMask),l.setOp(W.stencilFail,W.stencilZFail,W.stencilZPass)),Ie(W.polygonOffset,W.polygonOffsetFactor,W.polygonOffsetUnits),W.alphaToCoverage===!0?et(i.SAMPLE_ALPHA_TO_COVERAGE):pt(i.SAMPLE_ALPHA_TO_COVERAGE)}function jt(W){C!==W&&(W?i.frontFace(i.CW):i.frontFace(i.CCW),C=W)}function xe(W){W!==Cu?(et(i.CULL_FACE),W!==D&&(W===kc?i.cullFace(i.BACK):W===Pu?i.cullFace(i.FRONT):i.cullFace(i.FRONT_AND_BACK))):pt(i.CULL_FACE),D=W}function ze(W){W!==V&&(N&&i.lineWidth(W),V=W)}function Ie(W,Rt,ht){W?(et(i.POLYGON_OFFSET_FILL),(U!==Rt||z!==ht)&&(U=Rt,z=ht,a.getReversed()&&(Rt=-Rt),i.polygonOffset(Rt,ht))):pt(i.POLYGON_OFFSET_FILL)}function pe(W){W?et(i.SCISSOR_TEST):pt(i.SCISSOR_TEST)}function _e(W){W===void 0&&(W=i.TEXTURE0+q-1),K!==W&&(i.activeTexture(W),K=W)}function Y(W,Rt,ht){ht===void 0&&(K===null?ht=i.TEXTURE0+q-1:ht=K);let Tt=nt[ht];Tt===void 0&&(Tt={type:void 0,texture:void 0},nt[ht]=Tt),(Tt.type!==W||Tt.texture!==Rt)&&(K!==ht&&(i.activeTexture(ht),K=ht),i.bindTexture(W,Rt||J[W]),Tt.type=W,Tt.texture=Rt)}function Xe(){let W=nt[K];W!==void 0&&W.type!==void 0&&(i.bindTexture(W.type,null),W.type=void 0,W.texture=void 0)}function ye(){try{i.compressedTexImage2D(...arguments)}catch(W){Kt("WebGLState:",W)}}function L(){try{i.compressedTexImage3D(...arguments)}catch(W){Kt("WebGLState:",W)}}function y(){try{i.texSubImage2D(...arguments)}catch(W){Kt("WebGLState:",W)}}function $(){try{i.texSubImage3D(...arguments)}catch(W){Kt("WebGLState:",W)}}function Q(){try{i.compressedTexSubImage2D(...arguments)}catch(W){Kt("WebGLState:",W)}}function it(){try{i.compressedTexSubImage3D(...arguments)}catch(W){Kt("WebGLState:",W)}}function xt(){try{i.texStorage2D(...arguments)}catch(W){Kt("WebGLState:",W)}}function wt(){try{i.texStorage3D(...arguments)}catch(W){Kt("WebGLState:",W)}}function rt(){try{i.texImage2D(...arguments)}catch(W){Kt("WebGLState:",W)}}function ot(){try{i.texImage3D(...arguments)}catch(W){Kt("WebGLState:",W)}}function St(W){return f[W]!==void 0?f[W]:i.getParameter(W)}function Bt(W,Rt){f[W]!==Rt&&(i.pixelStorei(W,Rt),f[W]=Rt)}function Pt(W){zt.equals(W)===!1&&(i.scissor(W.x,W.y,W.z,W.w),zt.copy(W))}function Et(W){Lt.equals(W)===!1&&(i.viewport(W.x,W.y,W.z,W.w),Lt.copy(W))}function Ht(W,Rt){let ht=c.get(Rt);ht===void 0&&(ht=new WeakMap,c.set(Rt,ht));let Tt=ht.get(W);Tt===void 0&&(Tt=i.getUniformBlockIndex(Rt,W.name),ht.set(W,Tt))}function Vt(W,Rt){let Tt=c.get(Rt).get(W);o.get(Rt)!==Tt&&(i.uniformBlockBinding(Rt,Tt,W.__bindingPointIndex),o.set(Rt,Tt))}function Wt(){i.disable(i.BLEND),i.disable(i.CULL_FACE),i.disable(i.DEPTH_TEST),i.disable(i.POLYGON_OFFSET_FILL),i.disable(i.SCISSOR_TEST),i.disable(i.STENCIL_TEST),i.disable(i.SAMPLE_ALPHA_TO_COVERAGE),i.blendEquation(i.FUNC_ADD),i.blendFunc(i.ONE,i.ZERO),i.blendFuncSeparate(i.ONE,i.ZERO,i.ONE,i.ZERO),i.blendColor(0,0,0,0),i.colorMask(!0,!0,!0,!0),i.clearColor(0,0,0,0),i.depthMask(!0),i.depthFunc(i.LESS),a.setReversed(!1),i.clearDepth(1),i.stencilMask(4294967295),i.stencilFunc(i.ALWAYS,0,4294967295),i.stencilOp(i.KEEP,i.KEEP,i.KEEP),i.clearStencil(0),i.cullFace(i.BACK),i.frontFace(i.CCW),i.polygonOffset(0,0),i.activeTexture(i.TEXTURE0),i.bindFramebuffer(i.FRAMEBUFFER,null),i.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),i.bindFramebuffer(i.READ_FRAMEBUFFER,null),i.useProgram(null),i.lineWidth(1),i.scissor(0,0,i.canvas.width,i.canvas.height),i.viewport(0,0,i.canvas.width,i.canvas.height),i.pixelStorei(i.PACK_ALIGNMENT,4),i.pixelStorei(i.UNPACK_ALIGNMENT,4),i.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,!1),i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1),i.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,i.BROWSER_DEFAULT_WEBGL),i.pixelStorei(i.PACK_ROW_LENGTH,0),i.pixelStorei(i.PACK_SKIP_PIXELS,0),i.pixelStorei(i.PACK_SKIP_ROWS,0),i.pixelStorei(i.UNPACK_ROW_LENGTH,0),i.pixelStorei(i.UNPACK_IMAGE_HEIGHT,0),i.pixelStorei(i.UNPACK_SKIP_PIXELS,0),i.pixelStorei(i.UNPACK_SKIP_ROWS,0),i.pixelStorei(i.UNPACK_SKIP_IMAGES,0),h={},f={},K=null,nt={},d={},p=new WeakMap,x=[],M=null,m=!1,u=null,b=null,A=null,v=null,S=null,E=null,R=null,g=new $t(0,0,0),w=0,T=!1,C=null,D=null,V=null,U=null,z=null,zt.set(0,0,i.canvas.width,i.canvas.height),Lt.set(0,0,i.canvas.width,i.canvas.height),r.reset(),a.reset(),l.reset()}return{buffers:{color:r,depth:a,stencil:l},enable:et,disable:pt,bindFramebuffer:At,drawBuffers:Mt,useProgram:qt,setBlending:te,setMaterial:ne,setFlipSided:jt,setCullFace:xe,setLineWidth:ze,setPolygonOffset:Ie,setScissorTest:pe,activeTexture:_e,bindTexture:Y,unbindTexture:Xe,compressedTexImage2D:ye,compressedTexImage3D:L,texImage2D:rt,texImage3D:ot,pixelStorei:Bt,getParameter:St,updateUBOMapping:Ht,uniformBlockBinding:Vt,texStorage2D:xt,texStorage3D:wt,texSubImage2D:y,texSubImage3D:$,compressedTexSubImage2D:Q,compressedTexSubImage3D:it,scissor:Pt,viewport:Et,reset:Wt}}function E_(i,t,e,n,s,r,a){let l=t.has("WEBGL_multisampled_render_to_texture")?t.get("WEBGL_multisampled_render_to_texture"):null,o=typeof navigator>"u"?!1:/OculusBrowser/g.test(navigator.userAgent),c=new Xt,h=new WeakMap,f=new Set,d,p=new WeakMap,x=!1;try{x=typeof OffscreenCanvas<"u"&&new OffscreenCanvas(1,1).getContext("2d")!==null}catch{}function M(L,y){return x?new OffscreenCanvas(L,y):da("canvas")}function m(L,y,$){let Q=1,it=ye(L);if((it.width>$||it.height>$)&&(Q=$/Math.max(it.width,it.height)),Q<1)if(typeof HTMLImageElement<"u"&&L instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&L instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&L instanceof ImageBitmap||typeof VideoFrame<"u"&&L instanceof VideoFrame){let xt=Math.floor(Q*it.width),wt=Math.floor(Q*it.height);d===void 0&&(d=M(xt,wt));let rt=y?M(xt,wt):d;return rt.width=xt,rt.height=wt,rt.getContext("2d").drawImage(L,0,0,xt,wt),Zt("WebGLRenderer: Texture has been resized from ("+it.width+"x"+it.height+") to ("+xt+"x"+wt+")."),rt}else return"data"in L&&Zt("WebGLRenderer: Image in DataTexture is too big ("+it.width+"x"+it.height+")."),L;return L}function u(L){return L.generateMipmaps}function b(L){i.generateMipmap(L)}function A(L){return L.isWebGLCubeRenderTarget?i.TEXTURE_CUBE_MAP:L.isWebGL3DRenderTarget?i.TEXTURE_3D:L.isWebGLArrayRenderTarget||L.isCompressedArrayTexture?i.TEXTURE_2D_ARRAY:i.TEXTURE_2D}function v(L,y,$,Q,it,xt=!1){if(L!==null){if(i[L]!==void 0)return i[L];Zt("WebGLRenderer: Attempt to use non-existing WebGL internal format '"+L+"'")}let wt;Q&&(wt=t.get("EXT_texture_norm16"),wt||Zt("WebGLRenderer: Unable to use normalized textures without EXT_texture_norm16 extension"));let rt=y;if(y===i.RED&&($===i.FLOAT&&(rt=i.R32F),$===i.HALF_FLOAT&&(rt=i.R16F),$===i.UNSIGNED_BYTE&&(rt=i.R8),$===i.UNSIGNED_SHORT&&wt&&(rt=wt.R16_EXT),$===i.SHORT&&wt&&(rt=wt.R16_SNORM_EXT)),y===i.RED_INTEGER&&($===i.UNSIGNED_BYTE&&(rt=i.R8UI),$===i.UNSIGNED_SHORT&&(rt=i.R16UI),$===i.UNSIGNED_INT&&(rt=i.R32UI),$===i.BYTE&&(rt=i.R8I),$===i.SHORT&&(rt=i.R16I),$===i.INT&&(rt=i.R32I)),y===i.RG&&($===i.FLOAT&&(rt=i.RG32F),$===i.HALF_FLOAT&&(rt=i.RG16F),$===i.UNSIGNED_BYTE&&(rt=i.RG8),$===i.UNSIGNED_SHORT&&wt&&(rt=wt.RG16_EXT),$===i.SHORT&&wt&&(rt=wt.RG16_SNORM_EXT)),y===i.RG_INTEGER&&($===i.UNSIGNED_BYTE&&(rt=i.RG8UI),$===i.UNSIGNED_SHORT&&(rt=i.RG16UI),$===i.UNSIGNED_INT&&(rt=i.RG32UI),$===i.BYTE&&(rt=i.RG8I),$===i.SHORT&&(rt=i.RG16I),$===i.INT&&(rt=i.RG32I)),y===i.RGB_INTEGER&&($===i.UNSIGNED_BYTE&&(rt=i.RGB8UI),$===i.UNSIGNED_SHORT&&(rt=i.RGB16UI),$===i.UNSIGNED_INT&&(rt=i.RGB32UI),$===i.BYTE&&(rt=i.RGB8I),$===i.SHORT&&(rt=i.RGB16I),$===i.INT&&(rt=i.RGB32I)),y===i.RGBA_INTEGER&&($===i.UNSIGNED_BYTE&&(rt=i.RGBA8UI),$===i.UNSIGNED_SHORT&&(rt=i.RGBA16UI),$===i.UNSIGNED_INT&&(rt=i.RGBA32UI),$===i.BYTE&&(rt=i.RGBA8I),$===i.SHORT&&(rt=i.RGBA16I),$===i.INT&&(rt=i.RGBA32I)),y===i.RGB&&($===i.UNSIGNED_SHORT&&wt&&(rt=wt.RGB16_EXT),$===i.SHORT&&wt&&(rt=wt.RGB16_SNORM_EXT),$===i.UNSIGNED_INT_5_9_9_9_REV&&(rt=i.RGB9_E5),$===i.UNSIGNED_INT_10F_11F_11F_REV&&(rt=i.R11F_G11F_B10F)),y===i.RGBA){let ot=xt?ua:me.getTransfer(it);$===i.FLOAT&&(rt=i.RGBA32F),$===i.HALF_FLOAT&&(rt=i.RGBA16F),$===i.UNSIGNED_BYTE&&(rt=ot===Ae?i.SRGB8_ALPHA8:i.RGBA8),$===i.UNSIGNED_SHORT&&wt&&(rt=wt.RGBA16_EXT),$===i.SHORT&&wt&&(rt=wt.RGBA16_SNORM_EXT),$===i.UNSIGNED_SHORT_4_4_4_4&&(rt=i.RGBA4),$===i.UNSIGNED_SHORT_5_5_5_1&&(rt=i.RGB5_A1)}return(rt===i.R16F||rt===i.R32F||rt===i.RG16F||rt===i.RG32F||rt===i.RGBA16F||rt===i.RGBA32F)&&t.get("EXT_color_buffer_float"),rt}function S(L,y){let $;return L?y===null||y===di||y===Fr?$=i.DEPTH24_STENCIL8:y===Zn?$=i.DEPTH32F_STENCIL8:y===Ur&&($=i.DEPTH24_STENCIL8,Zt("DepthTexture: 16 bit depth attachment is not supported with stencil. Using 24-bit attachment.")):y===null||y===di||y===Fr?$=i.DEPTH_COMPONENT24:y===Zn?$=i.DEPTH_COMPONENT32F:y===Ur&&($=i.DEPTH_COMPONENT16),$}function E(L,y){return u(L)===!0||L.isFramebufferTexture&&L.minFilter!==an&&L.minFilter!==mn?Math.log2(Math.max(y.width,y.height))+1:L.mipmaps!==void 0&&L.mipmaps.length>0?L.mipmaps.length:L.isCompressedTexture&&Array.isArray(L.image)?y.mipmaps.length:1}function R(L){let y=L.target;y.removeEventListener("dispose",R),w(y),y.isVideoTexture&&h.delete(y),y.isHTMLTexture&&f.delete(y)}function g(L){let y=L.target;y.removeEventListener("dispose",g),C(y)}function w(L){let y=n.get(L);if(y.__webglInit===void 0)return;let $=L.source,Q=p.get($);if(Q){let it=Q[y.__cacheKey];it.usedTimes--,it.usedTimes===0&&T(L),Object.keys(Q).length===0&&p.delete($)}n.remove(L)}function T(L){let y=n.get(L);i.deleteTexture(y.__webglTexture);let $=L.source,Q=p.get($);delete Q[y.__cacheKey],a.memory.textures--}function C(L){let y=n.get(L);if(L.depthTexture&&(L.depthTexture.dispose(),n.remove(L.depthTexture)),L.isWebGLCubeRenderTarget)for(let Q=0;Q<6;Q++){if(Array.isArray(y.__webglFramebuffer[Q]))for(let it=0;it<y.__webglFramebuffer[Q].length;it++)i.deleteFramebuffer(y.__webglFramebuffer[Q][it]);else i.deleteFramebuffer(y.__webglFramebuffer[Q]);y.__webglDepthbuffer&&i.deleteRenderbuffer(y.__webglDepthbuffer[Q])}else{if(Array.isArray(y.__webglFramebuffer))for(let Q=0;Q<y.__webglFramebuffer.length;Q++)i.deleteFramebuffer(y.__webglFramebuffer[Q]);else i.deleteFramebuffer(y.__webglFramebuffer);if(y.__webglDepthbuffer&&i.deleteRenderbuffer(y.__webglDepthbuffer),y.__webglMultisampledFramebuffer&&i.deleteFramebuffer(y.__webglMultisampledFramebuffer),y.__webglColorRenderbuffer)for(let Q=0;Q<y.__webglColorRenderbuffer.length;Q++)y.__webglColorRenderbuffer[Q]&&i.deleteRenderbuffer(y.__webglColorRenderbuffer[Q]);y.__webglDepthRenderbuffer&&i.deleteRenderbuffer(y.__webglDepthRenderbuffer)}let $=L.textures;for(let Q=0,it=$.length;Q<it;Q++){let xt=n.get($[Q]);xt.__webglTexture&&(i.deleteTexture(xt.__webglTexture),a.memory.textures--),n.remove($[Q])}n.remove(L)}let D=0;function V(){D=0}function U(){return D}function z(L){D=L}function q(){let L=D;return L>=s.maxTextures&&Zt("WebGLTextures: Trying to use "+(L+1)+" texture units while this GPU supports only "+s.maxTextures),D+=1,L}function N(L){let y=[];return y.push(L.wrapS),y.push(L.wrapT),y.push(L.wrapR||0),y.push(L.magFilter),y.push(L.minFilter),y.push(L.anisotropy),y.push(L.internalFormat),y.push(L.format),y.push(L.type),y.push(L.generateMipmaps),y.push(L.premultiplyAlpha),y.push(L.flipY),y.push(L.unpackAlignment),y.push(L.colorSpace),y.join()}function G(L,y){let $=n.get(L);if(L.isVideoTexture&&Y(L),L.isRenderTargetTexture===!1&&L.isExternalTexture!==!0&&L.version>0&&$.__version!==L.version){let Q=L.image;if(Q===null)Zt("WebGLRenderer: Texture marked for update but no image data found.");else if(Q.complete===!1)Zt("WebGLRenderer: Texture marked for update but image is incomplete");else{pt($,L,y);return}}else L.isExternalTexture&&($.__webglTexture=L.sourceTexture?L.sourceTexture:null);e.bindTexture(i.TEXTURE_2D,$.__webglTexture,i.TEXTURE0+y)}function X(L,y){let $=n.get(L);if(L.isRenderTargetTexture===!1&&L.version>0&&$.__version!==L.version){pt($,L,y);return}else L.isExternalTexture&&($.__webglTexture=L.sourceTexture?L.sourceTexture:null);e.bindTexture(i.TEXTURE_2D_ARRAY,$.__webglTexture,i.TEXTURE0+y)}function K(L,y){let $=n.get(L);if(L.isRenderTargetTexture===!1&&L.version>0&&$.__version!==L.version){pt($,L,y);return}e.bindTexture(i.TEXTURE_3D,$.__webglTexture,i.TEXTURE0+y)}function nt(L,y){let $=n.get(L);if(L.isCubeDepthTexture!==!0&&L.version>0&&$.__version!==L.version){At($,L,y);return}e.bindTexture(i.TEXTURE_CUBE_MAP,$.__webglTexture,i.TEXTURE0+y)}let tt={[Si]:i.REPEAT,[Mi]:i.CLAMP_TO_EDGE,[wo]:i.MIRRORED_REPEAT},lt={[an]:i.NEAREST,[ju]:i.NEAREST_MIPMAP_NEAREST,[Ra]:i.NEAREST_MIPMAP_LINEAR,[mn]:i.LINEAR,[Ko]:i.LINEAR_MIPMAP_NEAREST,[Ms]:i.LINEAR_MIPMAP_LINEAR},zt={[nd]:i.NEVER,[od]:i.ALWAYS,[id]:i.LESS,[Nl]:i.LEQUAL,[sd]:i.EQUAL,[Ul]:i.GEQUAL,[rd]:i.GREATER,[ad]:i.NOTEQUAL};function Lt(L,y){if(y.type===Zn&&t.has("OES_texture_float_linear")===!1&&(y.magFilter===mn||y.magFilter===Ko||y.magFilter===Ra||y.magFilter===Ms||y.minFilter===mn||y.minFilter===Ko||y.minFilter===Ra||y.minFilter===Ms)&&Zt("WebGLRenderer: Unable to use linear filtering with floating point textures. OES_texture_float_linear not supported on this device."),i.texParameteri(L,i.TEXTURE_WRAP_S,tt[y.wrapS]),i.texParameteri(L,i.TEXTURE_WRAP_T,tt[y.wrapT]),(L===i.TEXTURE_3D||L===i.TEXTURE_2D_ARRAY)&&i.texParameteri(L,i.TEXTURE_WRAP_R,tt[y.wrapR]),i.texParameteri(L,i.TEXTURE_MAG_FILTER,lt[y.magFilter]),i.texParameteri(L,i.TEXTURE_MIN_FILTER,lt[y.minFilter]),y.compareFunction&&(i.texParameteri(L,i.TEXTURE_COMPARE_MODE,i.COMPARE_REF_TO_TEXTURE),i.texParameteri(L,i.TEXTURE_COMPARE_FUNC,zt[y.compareFunction])),t.has("EXT_texture_filter_anisotropic")===!0){if(y.magFilter===an||y.minFilter!==Ra&&y.minFilter!==Ms||y.type===Zn&&t.has("OES_texture_float_linear")===!1)return;if(y.anisotropy>1||n.get(y).__currentAnisotropy){let $=t.get("EXT_texture_filter_anisotropic");i.texParameterf(L,$.TEXTURE_MAX_ANISOTROPY_EXT,Math.min(y.anisotropy,s.getMaxAnisotropy())),n.get(y).__currentAnisotropy=y.anisotropy}}}function gt(L,y){let $=!1;L.__webglInit===void 0&&(L.__webglInit=!0,y.addEventListener("dispose",R));let Q=y.source,it=p.get(Q);it===void 0&&(it={},p.set(Q,it));let xt=N(y);if(xt!==L.__cacheKey){it[xt]===void 0&&(it[xt]={texture:i.createTexture(),usedTimes:0},a.memory.textures++,$=!0),it[xt].usedTimes++;let wt=it[L.__cacheKey];wt!==void 0&&(it[L.__cacheKey].usedTimes--,wt.usedTimes===0&&T(y)),L.__cacheKey=xt,L.__webglTexture=it[xt].texture}return $}function J(L,y,$){return Math.floor(Math.floor(L/$)/y)}function et(L,y,$,Q){let xt=L.updateRanges;if(xt.length===0)e.texSubImage2D(i.TEXTURE_2D,0,0,0,y.width,y.height,$,Q,y.data);else{xt.sort((Bt,Pt)=>Bt.start-Pt.start);let wt=0;for(let Bt=1;Bt<xt.length;Bt++){let Pt=xt[wt],Et=xt[Bt],Ht=Pt.start+Pt.count,Vt=J(Et.start,y.width,4),Wt=J(Pt.start,y.width,4);Et.start<=Ht+1&&Vt===Wt&&J(Et.start+Et.count-1,y.width,4)===Vt?Pt.count=Math.max(Pt.count,Et.start+Et.count-Pt.start):(++wt,xt[wt]=Et)}xt.length=wt+1;let rt=e.getParameter(i.UNPACK_ROW_LENGTH),ot=e.getParameter(i.UNPACK_SKIP_PIXELS),St=e.getParameter(i.UNPACK_SKIP_ROWS);e.pixelStorei(i.UNPACK_ROW_LENGTH,y.width);for(let Bt=0,Pt=xt.length;Bt<Pt;Bt++){let Et=xt[Bt],Ht=Math.floor(Et.start/4),Vt=Math.ceil(Et.count/4),Wt=Ht%y.width,W=Math.floor(Ht/y.width),Rt=Vt,ht=1;e.pixelStorei(i.UNPACK_SKIP_PIXELS,Wt),e.pixelStorei(i.UNPACK_SKIP_ROWS,W),e.texSubImage2D(i.TEXTURE_2D,0,Wt,W,Rt,ht,$,Q,y.data)}L.clearUpdateRanges(),e.pixelStorei(i.UNPACK_ROW_LENGTH,rt),e.pixelStorei(i.UNPACK_SKIP_PIXELS,ot),e.pixelStorei(i.UNPACK_SKIP_ROWS,St)}}function pt(L,y,$){let Q=i.TEXTURE_2D;(y.isDataArrayTexture||y.isCompressedArrayTexture)&&(Q=i.TEXTURE_2D_ARRAY),y.isData3DTexture&&(Q=i.TEXTURE_3D);let it=gt(L,y),xt=y.source;e.bindTexture(Q,L.__webglTexture,i.TEXTURE0+$);let wt=n.get(xt);if(xt.version!==wt.__version||it===!0){if(e.activeTexture(i.TEXTURE0+$),(typeof ImageBitmap<"u"&&y.image instanceof ImageBitmap)===!1){let ht=me.getPrimaries(me.workingColorSpace),Tt=y.colorSpace===$i?null:me.getPrimaries(y.colorSpace),It=y.colorSpace===$i||ht===Tt?i.NONE:i.BROWSER_DEFAULT_WEBGL;e.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,y.flipY),e.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,y.premultiplyAlpha),e.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,It)}e.pixelStorei(i.UNPACK_ALIGNMENT,y.unpackAlignment);let ot=m(y.image,!1,s.maxTextureSize);ot=Xe(y,ot);let St=r.convert(y.format,y.colorSpace),Bt=r.convert(y.type),Pt=v(y.internalFormat,St,Bt,y.normalized,y.colorSpace,y.isVideoTexture);Lt(Q,y);let Et,Ht=y.mipmaps,Vt=y.isVideoTexture!==!0,Wt=wt.__version===void 0||it===!0,W=xt.dataReady,Rt=E(y,ot);if(y.isDepthTexture)Pt=S(y.format===Ss,y.type),Wt&&(Vt?e.texStorage2D(i.TEXTURE_2D,1,Pt,ot.width,ot.height):e.texImage2D(i.TEXTURE_2D,0,Pt,ot.width,ot.height,0,St,Bt,null));else if(y.isDataTexture)if(Ht.length>0){Vt&&Wt&&e.texStorage2D(i.TEXTURE_2D,Rt,Pt,Ht[0].width,Ht[0].height);for(let ht=0,Tt=Ht.length;ht<Tt;ht++)Et=Ht[ht],Vt?W&&e.texSubImage2D(i.TEXTURE_2D,ht,0,0,Et.width,Et.height,St,Bt,Et.data):e.texImage2D(i.TEXTURE_2D,ht,Pt,Et.width,Et.height,0,St,Bt,Et.data);y.generateMipmaps=!1}else Vt?(Wt&&e.texStorage2D(i.TEXTURE_2D,Rt,Pt,ot.width,ot.height),W&&et(y,ot,St,Bt)):e.texImage2D(i.TEXTURE_2D,0,Pt,ot.width,ot.height,0,St,Bt,ot.data);else if(y.isCompressedTexture)if(y.isCompressedArrayTexture){Vt&&Wt&&e.texStorage3D(i.TEXTURE_2D_ARRAY,Rt,Pt,Ht[0].width,Ht[0].height,ot.depth);for(let ht=0,Tt=Ht.length;ht<Tt;ht++)if(Et=Ht[ht],y.format!==$n)if(St!==null)if(Vt){if(W)if(y.layerUpdates.size>0){let It=dh(Et.width,Et.height,y.format,y.type);for(let B of y.layerUpdates){let at=Et.data.subarray(B*It/Et.data.BYTES_PER_ELEMENT,(B+1)*It/Et.data.BYTES_PER_ELEMENT);e.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,ht,0,0,B,Et.width,Et.height,1,St,at)}}else e.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,ht,0,0,0,Et.width,Et.height,ot.depth,St,Et.data)}else e.compressedTexImage3D(i.TEXTURE_2D_ARRAY,ht,Pt,Et.width,Et.height,ot.depth,0,Et.data,0,0);else Zt("WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()");else Vt?W&&e.texSubImage3D(i.TEXTURE_2D_ARRAY,ht,0,0,0,Et.width,Et.height,ot.depth,St,Bt,Et.data):e.texImage3D(i.TEXTURE_2D_ARRAY,ht,Pt,Et.width,Et.height,ot.depth,0,St,Bt,Et.data);y.layerUpdates.size>0&&y.clearLayerUpdates()}else{Vt&&Wt&&e.texStorage2D(i.TEXTURE_2D,Rt,Pt,Ht[0].width,Ht[0].height);for(let ht=0,Tt=Ht.length;ht<Tt;ht++)Et=Ht[ht],y.format!==$n?St!==null?Vt?W&&e.compressedTexSubImage2D(i.TEXTURE_2D,ht,0,0,Et.width,Et.height,St,Et.data):e.compressedTexImage2D(i.TEXTURE_2D,ht,Pt,Et.width,Et.height,0,Et.data):Zt("WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()"):Vt?W&&e.texSubImage2D(i.TEXTURE_2D,ht,0,0,Et.width,Et.height,St,Bt,Et.data):e.texImage2D(i.TEXTURE_2D,ht,Pt,Et.width,Et.height,0,St,Bt,Et.data)}else if(y.isDataArrayTexture)if(Vt){if(Wt&&e.texStorage3D(i.TEXTURE_2D_ARRAY,Rt,Pt,ot.width,ot.height,ot.depth),W)if(y.layerUpdates.size>0){let ht=dh(ot.width,ot.height,y.format,y.type);for(let Tt of y.layerUpdates){let It=ot.data.subarray(Tt*ht/ot.data.BYTES_PER_ELEMENT,(Tt+1)*ht/ot.data.BYTES_PER_ELEMENT);e.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,Tt,ot.width,ot.height,1,St,Bt,It)}y.clearLayerUpdates()}else e.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,0,ot.width,ot.height,ot.depth,St,Bt,ot.data)}else e.texImage3D(i.TEXTURE_2D_ARRAY,0,Pt,ot.width,ot.height,ot.depth,0,St,Bt,ot.data);else if(y.isData3DTexture)Vt?(Wt&&e.texStorage3D(i.TEXTURE_3D,Rt,Pt,ot.width,ot.height,ot.depth),W&&e.texSubImage3D(i.TEXTURE_3D,0,0,0,0,ot.width,ot.height,ot.depth,St,Bt,ot.data)):e.texImage3D(i.TEXTURE_3D,0,Pt,ot.width,ot.height,ot.depth,0,St,Bt,ot.data);else if(y.isFramebufferTexture){if(Wt)if(Vt)e.texStorage2D(i.TEXTURE_2D,Rt,Pt,ot.width,ot.height);else{let ht=ot.width,Tt=ot.height;for(let It=0;It<Rt;It++)e.texImage2D(i.TEXTURE_2D,It,Pt,ht,Tt,0,St,Bt,null),ht>>=1,Tt>>=1}}else if(y.isHTMLTexture){if("texElementImage2D"in i){let ht=i.canvas;if(ht.hasAttribute("layoutsubtree")||ht.setAttribute("layoutsubtree","true"),ot.parentNode!==ht){ht.appendChild(ot),f.add(y),ht.onpaint=Tt=>{let It=Tt.changedElements;for(let B of f)It.includes(B.image)&&(B.needsUpdate=!0)},ht.requestPaint();return}if(i.texElementImage2D.length===3)i.texElementImage2D(i.TEXTURE_2D,i.RGBA8,ot);else{let It=i.RGBA,B=i.RGBA,at=i.UNSIGNED_BYTE;i.texElementImage2D(i.TEXTURE_2D,0,It,B,at,ot)}i.texParameteri(i.TEXTURE_2D,i.TEXTURE_MIN_FILTER,i.LINEAR),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_S,i.CLAMP_TO_EDGE),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_T,i.CLAMP_TO_EDGE)}}else if(Ht.length>0){if(Vt&&Wt){let ht=ye(Ht[0]);e.texStorage2D(i.TEXTURE_2D,Rt,Pt,ht.width,ht.height)}for(let ht=0,Tt=Ht.length;ht<Tt;ht++)Et=Ht[ht],Vt?W&&e.texSubImage2D(i.TEXTURE_2D,ht,0,0,St,Bt,Et):e.texImage2D(i.TEXTURE_2D,ht,Pt,St,Bt,Et);y.generateMipmaps=!1}else if(Vt){if(Wt){let ht=ye(ot);e.texStorage2D(i.TEXTURE_2D,Rt,Pt,ht.width,ht.height)}W&&e.texSubImage2D(i.TEXTURE_2D,0,0,0,St,Bt,ot)}else e.texImage2D(i.TEXTURE_2D,0,Pt,St,Bt,ot);u(y)&&b(Q),wt.__version=xt.version,y.onUpdate&&y.onUpdate(y)}L.__version=y.version}function At(L,y,$){if(y.image.length!==6)return;let Q=gt(L,y),it=y.source;e.bindTexture(i.TEXTURE_CUBE_MAP,L.__webglTexture,i.TEXTURE0+$);let xt=n.get(it);if(it.version!==xt.__version||Q===!0){e.activeTexture(i.TEXTURE0+$);let wt=me.getPrimaries(me.workingColorSpace),rt=y.colorSpace===$i?null:me.getPrimaries(y.colorSpace),ot=y.colorSpace===$i||wt===rt?i.NONE:i.BROWSER_DEFAULT_WEBGL;e.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,y.flipY),e.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,y.premultiplyAlpha),e.pixelStorei(i.UNPACK_ALIGNMENT,y.unpackAlignment),e.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,ot);let St=y.isCompressedTexture||y.image[0].isCompressedTexture,Bt=y.image[0]&&y.image[0].isDataTexture,Pt=[];for(let B=0;B<6;B++)!St&&!Bt?Pt[B]=m(y.image[B],!0,s.maxCubemapSize):Pt[B]=Bt?y.image[B].image:y.image[B],Pt[B]=Xe(y,Pt[B]);let Et=Pt[0],Ht=r.convert(y.format,y.colorSpace),Vt=r.convert(y.type),Wt=v(y.internalFormat,Ht,Vt,y.normalized,y.colorSpace),W=y.isVideoTexture!==!0,Rt=xt.__version===void 0||Q===!0,ht=it.dataReady,Tt=E(y,Et);Lt(i.TEXTURE_CUBE_MAP,y);let It;if(St){W&&Rt&&e.texStorage2D(i.TEXTURE_CUBE_MAP,Tt,Wt,Et.width,Et.height);for(let B=0;B<6;B++){It=Pt[B].mipmaps;for(let at=0;at<It.length;at++){let ut=It[at];y.format!==$n?Ht!==null?W?ht&&e.compressedTexSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,at,0,0,ut.width,ut.height,Ht,ut.data):e.compressedTexImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,at,Wt,ut.width,ut.height,0,ut.data):Zt("WebGLRenderer: Attempt to load unsupported compressed texture format in .setTextureCube()"):W?ht&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,at,0,0,ut.width,ut.height,Ht,Vt,ut.data):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,at,Wt,ut.width,ut.height,0,Ht,Vt,ut.data)}}}else{if(It=y.mipmaps,W&&Rt){It.length>0&&Tt++;let B=ye(Pt[0]);e.texStorage2D(i.TEXTURE_CUBE_MAP,Tt,Wt,B.width,B.height)}for(let B=0;B<6;B++)if(Bt){W?ht&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,0,0,0,Pt[B].width,Pt[B].height,Ht,Vt,Pt[B].data):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,0,Wt,Pt[B].width,Pt[B].height,0,Ht,Vt,Pt[B].data);for(let at=0;at<It.length;at++){let mt=It[at].image[B].image;W?ht&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,at+1,0,0,mt.width,mt.height,Ht,Vt,mt.data):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,at+1,Wt,mt.width,mt.height,0,Ht,Vt,mt.data)}}else{W?ht&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,0,0,0,Ht,Vt,Pt[B]):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,0,Wt,Ht,Vt,Pt[B]);for(let at=0;at<It.length;at++){let ut=It[at];W?ht&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,at+1,0,0,Ht,Vt,ut.image[B]):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+B,at+1,Wt,Ht,Vt,ut.image[B])}}}u(y)&&b(i.TEXTURE_CUBE_MAP),xt.__version=it.version,y.onUpdate&&y.onUpdate(y)}L.__version=y.version}function Mt(L,y,$,Q,it,xt){let wt=r.convert($.format,$.colorSpace),rt=r.convert($.type),ot=v($.internalFormat,wt,rt,$.normalized,$.colorSpace),St=n.get(y),Bt=n.get($);if(Bt.__renderTarget=y,!St.__hasExternalTextures){let Pt=Math.max(1,y.width>>xt),Et=Math.max(1,y.height>>xt);it===i.TEXTURE_3D||it===i.TEXTURE_2D_ARRAY?e.texImage3D(it,xt,ot,Pt,Et,y.depth,0,wt,rt,null):e.texImage2D(it,xt,ot,Pt,Et,0,wt,rt,null)}e.bindFramebuffer(i.FRAMEBUFFER,L),_e(y)?l.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,Q,it,Bt.__webglTexture,0,pe(y)):(it===i.TEXTURE_2D||it>=i.TEXTURE_CUBE_MAP_POSITIVE_X&&it<=i.TEXTURE_CUBE_MAP_NEGATIVE_Z)&&i.framebufferTexture2D(i.FRAMEBUFFER,Q,it,Bt.__webglTexture,xt),e.bindFramebuffer(i.FRAMEBUFFER,null)}function qt(L,y,$){if(i.bindRenderbuffer(i.RENDERBUFFER,L),y.depthBuffer){let Q=y.depthTexture,it=Q&&Q.isDepthTexture?Q.type:null,xt=S(y.stencilBuffer,it),wt=y.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT;_e(y)?l.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,pe(y),xt,y.width,y.height):$?i.renderbufferStorageMultisample(i.RENDERBUFFER,pe(y),xt,y.width,y.height):i.renderbufferStorage(i.RENDERBUFFER,xt,y.width,y.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,wt,i.RENDERBUFFER,L)}else{let Q=y.textures;for(let it=0;it<Q.length;it++){let xt=Q[it],wt=r.convert(xt.format,xt.colorSpace),rt=r.convert(xt.type),ot=v(xt.internalFormat,wt,rt,xt.normalized,xt.colorSpace);_e(y)?l.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,pe(y),ot,y.width,y.height):$?i.renderbufferStorageMultisample(i.RENDERBUFFER,pe(y),ot,y.width,y.height):i.renderbufferStorage(i.RENDERBUFFER,ot,y.width,y.height)}}i.bindRenderbuffer(i.RENDERBUFFER,null)}function ve(L,y,$){let Q=y.isWebGLCubeRenderTarget===!0;if(e.bindFramebuffer(i.FRAMEBUFFER,L),!(y.depthTexture&&y.depthTexture.isDepthTexture))throw new Error("THREE.WebGLTextures: renderTarget.depthTexture must be an instance of THREE.DepthTexture.");let it=n.get(y.depthTexture);if(it.__renderTarget=y,(!it.__webglTexture||y.depthTexture.image.width!==y.width||y.depthTexture.image.height!==y.height)&&(y.depthTexture.image.width=y.width,y.depthTexture.image.height=y.height,y.depthTexture.needsUpdate=!0),Q){if(it.__webglInit===void 0&&(it.__webglInit=!0,y.depthTexture.addEventListener("dispose",R)),it.__webglTexture===void 0){it.__webglTexture=i.createTexture(),e.bindTexture(i.TEXTURE_CUBE_MAP,it.__webglTexture),Lt(i.TEXTURE_CUBE_MAP,y.depthTexture);let St=r.convert(y.depthTexture.format),Bt=r.convert(y.depthTexture.type),Pt;y.depthTexture.format===Ei?Pt=i.DEPTH_COMPONENT24:y.depthTexture.format===Ss&&(Pt=i.DEPTH24_STENCIL8);for(let Et=0;Et<6;Et++)i.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Et,0,Pt,y.width,y.height,0,St,Bt,null)}}else G(y.depthTexture,0);let xt=it.__webglTexture,wt=pe(y),rt=Q?i.TEXTURE_CUBE_MAP_POSITIVE_X+$:i.TEXTURE_2D,ot=y.depthTexture.format===Ss?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT;if(y.depthTexture.format===Ei)_e(y)?l.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,ot,rt,xt,0,wt):i.framebufferTexture2D(i.FRAMEBUFFER,ot,rt,xt,0);else if(y.depthTexture.format===Ss)_e(y)?l.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,ot,rt,xt,0,wt):i.framebufferTexture2D(i.FRAMEBUFFER,ot,rt,xt,0);else throw new Error("THREE.WebGLTextures: Unknown depthTexture format.")}function Jt(L){let y=n.get(L),$=L.isWebGLCubeRenderTarget===!0;if(y.__boundDepthTexture!==L.depthTexture){let Q=L.depthTexture;if(y.__depthDisposeCallback&&y.__depthDisposeCallback(),Q){let it=()=>{delete y.__boundDepthTexture,delete y.__depthDisposeCallback,Q.removeEventListener("dispose",it)};Q.addEventListener("dispose",it),y.__depthDisposeCallback=it}y.__boundDepthTexture=Q}if(L.depthTexture&&!y.__autoAllocateDepthBuffer)if($)for(let Q=0;Q<6;Q++)ve(y.__webglFramebuffer[Q],L,Q);else{let Q=L.texture.mipmaps;Q&&Q.length>0?ve(y.__webglFramebuffer[0],L,0):ve(y.__webglFramebuffer,L,0)}else if($){y.__webglDepthbuffer=[];for(let Q=0;Q<6;Q++)if(e.bindFramebuffer(i.FRAMEBUFFER,y.__webglFramebuffer[Q]),y.__webglDepthbuffer[Q]===void 0)y.__webglDepthbuffer[Q]=i.createRenderbuffer(),qt(y.__webglDepthbuffer[Q],L,!1);else{let it=L.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,xt=y.__webglDepthbuffer[Q];i.bindRenderbuffer(i.RENDERBUFFER,xt),i.framebufferRenderbuffer(i.FRAMEBUFFER,it,i.RENDERBUFFER,xt)}}else{let Q=L.texture.mipmaps;if(Q&&Q.length>0?e.bindFramebuffer(i.FRAMEBUFFER,y.__webglFramebuffer[0]):e.bindFramebuffer(i.FRAMEBUFFER,y.__webglFramebuffer),y.__webglDepthbuffer===void 0)y.__webglDepthbuffer=i.createRenderbuffer(),qt(y.__webglDepthbuffer,L,!1);else{let it=L.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,xt=y.__webglDepthbuffer;i.bindRenderbuffer(i.RENDERBUFFER,xt),i.framebufferRenderbuffer(i.FRAMEBUFFER,it,i.RENDERBUFFER,xt)}}e.bindFramebuffer(i.FRAMEBUFFER,null)}function te(L,y,$){let Q=n.get(L);y!==void 0&&Mt(Q.__webglFramebuffer,L,L.texture,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,0),$!==void 0&&Jt(L)}function ne(L){let y=L.texture,$=n.get(L),Q=n.get(y);L.addEventListener("dispose",g);let it=L.textures,xt=L.isWebGLCubeRenderTarget===!0,wt=it.length>1;if(wt||(Q.__webglTexture===void 0&&(Q.__webglTexture=i.createTexture()),Q.__version=y.version,a.memory.textures++),xt){$.__webglFramebuffer=[];for(let rt=0;rt<6;rt++)if(y.mipmaps&&y.mipmaps.length>0){$.__webglFramebuffer[rt]=[];for(let ot=0;ot<y.mipmaps.length;ot++)$.__webglFramebuffer[rt][ot]=i.createFramebuffer()}else $.__webglFramebuffer[rt]=i.createFramebuffer()}else{if(y.mipmaps&&y.mipmaps.length>0){$.__webglFramebuffer=[];for(let rt=0;rt<y.mipmaps.length;rt++)$.__webglFramebuffer[rt]=i.createFramebuffer()}else $.__webglFramebuffer=i.createFramebuffer();if(wt)for(let rt=0,ot=it.length;rt<ot;rt++){let St=n.get(it[rt]);St.__webglTexture===void 0&&(St.__webglTexture=i.createTexture(),a.memory.textures++)}if(L.samples>0&&_e(L)===!1){$.__webglMultisampledFramebuffer=i.createFramebuffer(),$.__webglColorRenderbuffer=[],e.bindFramebuffer(i.FRAMEBUFFER,$.__webglMultisampledFramebuffer);for(let rt=0;rt<it.length;rt++){let ot=it[rt];$.__webglColorRenderbuffer[rt]=i.createRenderbuffer(),i.bindRenderbuffer(i.RENDERBUFFER,$.__webglColorRenderbuffer[rt]);let St=r.convert(ot.format,ot.colorSpace),Bt=r.convert(ot.type),Pt=v(ot.internalFormat,St,Bt,ot.normalized,ot.colorSpace,L.isXRRenderTarget===!0),Et=pe(L);i.renderbufferStorageMultisample(i.RENDERBUFFER,Et,Pt,L.width,L.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+rt,i.RENDERBUFFER,$.__webglColorRenderbuffer[rt])}i.bindRenderbuffer(i.RENDERBUFFER,null),L.depthBuffer&&($.__webglDepthRenderbuffer=i.createRenderbuffer(),qt($.__webglDepthRenderbuffer,L,!0)),e.bindFramebuffer(i.FRAMEBUFFER,null)}}if(xt){e.bindTexture(i.TEXTURE_CUBE_MAP,Q.__webglTexture),Lt(i.TEXTURE_CUBE_MAP,y);for(let rt=0;rt<6;rt++)if(y.mipmaps&&y.mipmaps.length>0)for(let ot=0;ot<y.mipmaps.length;ot++)Mt($.__webglFramebuffer[rt][ot],L,y,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+rt,ot);else Mt($.__webglFramebuffer[rt],L,y,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+rt,0);u(y)&&b(i.TEXTURE_CUBE_MAP),e.unbindTexture()}else if(wt){for(let rt=0,ot=it.length;rt<ot;rt++){let St=it[rt],Bt=n.get(St),Pt=i.TEXTURE_2D;(L.isWebGL3DRenderTarget||L.isWebGLArrayRenderTarget)&&(Pt=L.isWebGL3DRenderTarget?i.TEXTURE_3D:i.TEXTURE_2D_ARRAY),e.bindTexture(Pt,Bt.__webglTexture),Lt(Pt,St),Mt($.__webglFramebuffer,L,St,i.COLOR_ATTACHMENT0+rt,Pt,0),u(St)&&b(Pt)}e.unbindTexture()}else{let rt=i.TEXTURE_2D;if((L.isWebGL3DRenderTarget||L.isWebGLArrayRenderTarget)&&(rt=L.isWebGL3DRenderTarget?i.TEXTURE_3D:i.TEXTURE_2D_ARRAY),e.bindTexture(rt,Q.__webglTexture),Lt(rt,y),y.mipmaps&&y.mipmaps.length>0)for(let ot=0;ot<y.mipmaps.length;ot++)Mt($.__webglFramebuffer[ot],L,y,i.COLOR_ATTACHMENT0,rt,ot);else Mt($.__webglFramebuffer,L,y,i.COLOR_ATTACHMENT0,rt,0);u(y)&&b(rt),e.unbindTexture()}L.depthBuffer&&Jt(L)}function jt(L){let y=L.textures;for(let $=0,Q=y.length;$<Q;$++){let it=y[$];if(u(it)){let xt=A(L),wt=n.get(it).__webglTexture;e.bindTexture(xt,wt),b(xt),e.unbindTexture()}}}let xe=[],ze=[];function Ie(L){if(L.samples>0){if(_e(L)===!1){let y=L.textures,$=L.width,Q=L.height,it=i.COLOR_BUFFER_BIT,xt=L.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,wt=n.get(L),rt=y.length>1;if(rt)for(let St=0;St<y.length;St++)e.bindFramebuffer(i.FRAMEBUFFER,wt.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+St,i.RENDERBUFFER,null),e.bindFramebuffer(i.FRAMEBUFFER,wt.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+St,i.TEXTURE_2D,null,0);e.bindFramebuffer(i.READ_FRAMEBUFFER,wt.__webglMultisampledFramebuffer);let ot=L.texture.mipmaps;ot&&ot.length>0?e.bindFramebuffer(i.DRAW_FRAMEBUFFER,wt.__webglFramebuffer[0]):e.bindFramebuffer(i.DRAW_FRAMEBUFFER,wt.__webglFramebuffer);for(let St=0;St<y.length;St++){if(L.resolveDepthBuffer&&(L.depthBuffer&&(it|=i.DEPTH_BUFFER_BIT),L.stencilBuffer&&L.resolveStencilBuffer&&(it|=i.STENCIL_BUFFER_BIT)),rt){i.framebufferRenderbuffer(i.READ_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.RENDERBUFFER,wt.__webglColorRenderbuffer[St]);let Bt=n.get(y[St]).__webglTexture;i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,Bt,0)}i.blitFramebuffer(0,0,$,Q,0,0,$,Q,it,i.NEAREST),o===!0&&(xe.length=0,ze.length=0,xe.push(i.COLOR_ATTACHMENT0+St),L.depthBuffer&&L.storeMultisampledDepthBuffer===!1&&(xe.push(xt),ze.push(xt),i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,ze)),i.invalidateFramebuffer(i.READ_FRAMEBUFFER,xe))}if(e.bindFramebuffer(i.READ_FRAMEBUFFER,null),e.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),rt)for(let St=0;St<y.length;St++){e.bindFramebuffer(i.FRAMEBUFFER,wt.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+St,i.RENDERBUFFER,wt.__webglColorRenderbuffer[St]);let Bt=n.get(y[St]).__webglTexture;e.bindFramebuffer(i.FRAMEBUFFER,wt.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+St,i.TEXTURE_2D,Bt,0)}e.bindFramebuffer(i.DRAW_FRAMEBUFFER,wt.__webglMultisampledFramebuffer)}else if(L.depthBuffer&&L.storeMultisampledDepthBuffer===!1&&o){let y=L.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT;i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,[y])}}}function pe(L){return Math.min(s.maxSamples,L.samples)}function _e(L){let y=n.get(L);return L.samples>0&&t.has("WEBGL_multisampled_render_to_texture")===!0&&y.__useRenderToTexture!==!1}function Y(L){let y=a.render.frame;h.get(L)!==y&&(h.set(L,y),L.update())}function Xe(L,y){let $=L.colorSpace,Q=L.format,it=L.type;return L.isCompressedTexture===!0||L.isVideoTexture===!0||$!==ha&&$!==$i&&(me.getTransfer($)===Ae?(Q!==$n||it!==Dn)&&Zt("WebGLTextures: sRGB encoded textures have to use RGBAFormat and UnsignedByteType."):Kt("WebGLTextures: Unsupported texture color space:",$)),y}function ye(L){return typeof HTMLImageElement<"u"&&L instanceof HTMLImageElement?(c.width=L.naturalWidth||L.width,c.height=L.naturalHeight||L.height):typeof VideoFrame<"u"&&L instanceof VideoFrame?(c.width=L.displayWidth,c.height=L.displayHeight):(c.width=L.width,c.height=L.height),c}this.allocateTextureUnit=q,this.resetTextureUnits=V,this.getTextureUnits=U,this.setTextureUnits=z,this.setTexture2D=G,this.setTexture2DArray=X,this.setTexture3D=K,this.setTextureCube=nt,this.rebindTextures=te,this.setupRenderTarget=ne,this.updateRenderTargetMipmap=jt,this.updateMultisampleRenderTarget=Ie,this.setupDepthRenderbuffer=Jt,this.setupFrameBufferTexture=Mt,this.useMultisampledRTT=_e,this.isReversedDepthBuffer=function(){return e.buffers.depth.getReversed()}}function w_(i,t){function e(n,s=$i){let r,a=me.getTransfer(s);if(n===Dn)return i.UNSIGNED_BYTE;if(n===jo)return i.UNSIGNED_SHORT_4_4_4_4;if(n===Qo)return i.UNSIGNED_SHORT_5_5_5_1;if(n===nh)return i.UNSIGNED_INT_5_9_9_9_REV;if(n===ih)return i.UNSIGNED_INT_10F_11F_11F_REV;if(n===th)return i.BYTE;if(n===eh)return i.SHORT;if(n===Ur)return i.UNSIGNED_SHORT;if(n===Jo)return i.INT;if(n===di)return i.UNSIGNED_INT;if(n===Zn)return i.FLOAT;if(n===fi)return i.HALF_FLOAT;if(n===sh)return i.ALPHA;if(n===rh)return i.RGB;if(n===$n)return i.RGBA;if(n===Ei)return i.DEPTH_COMPONENT;if(n===Ss)return i.DEPTH_STENCIL;if(n===tl)return i.RED;if(n===el)return i.RED_INTEGER;if(n===Es)return i.RG;if(n===nl)return i.RG_INTEGER;if(n===il)return i.RGBA_INTEGER;if(n===Ca||n===Pa||n===Ia||n===La)if(a===Ae)if(r=t.get("WEBGL_compressed_texture_s3tc_srgb"),r!==null){if(n===Ca)return r.COMPRESSED_SRGB_S3TC_DXT1_EXT;if(n===Pa)return r.COMPRESSED_SRGB_ALPHA_S3TC_DXT1_EXT;if(n===Ia)return r.COMPRESSED_SRGB_ALPHA_S3TC_DXT3_EXT;if(n===La)return r.COMPRESSED_SRGB_ALPHA_S3TC_DXT5_EXT}else return null;else if(r=t.get("WEBGL_compressed_texture_s3tc"),r!==null){if(n===Ca)return r.COMPRESSED_RGB_S3TC_DXT1_EXT;if(n===Pa)return r.COMPRESSED_RGBA_S3TC_DXT1_EXT;if(n===Ia)return r.COMPRESSED_RGBA_S3TC_DXT3_EXT;if(n===La)return r.COMPRESSED_RGBA_S3TC_DXT5_EXT}else return null;if(n===sl||n===rl||n===al||n===ol)if(r=t.get("WEBGL_compressed_texture_pvrtc"),r!==null){if(n===sl)return r.COMPRESSED_RGB_PVRTC_4BPPV1_IMG;if(n===rl)return r.COMPRESSED_RGB_PVRTC_2BPPV1_IMG;if(n===al)return r.COMPRESSED_RGBA_PVRTC_4BPPV1_IMG;if(n===ol)return r.COMPRESSED_RGBA_PVRTC_2BPPV1_IMG}else return null;if(n===ll||n===cl||n===hl||n===ul||n===dl||n===za||n===fl)if(r=t.get("WEBGL_compressed_texture_etc"),r!==null){if(n===ll||n===cl)return a===Ae?r.COMPRESSED_SRGB8_ETC2:r.COMPRESSED_RGB8_ETC2;if(n===hl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ETC2_EAC:r.COMPRESSED_RGBA8_ETC2_EAC;if(n===ul)return r.COMPRESSED_R11_EAC;if(n===dl)return r.COMPRESSED_SIGNED_R11_EAC;if(n===za)return r.COMPRESSED_RG11_EAC;if(n===fl)return r.COMPRESSED_SIGNED_RG11_EAC}else return null;if(n===pl||n===ml||n===gl||n===xl||n===_l||n===yl||n===vl||n===bl||n===Ml||n===Sl||n===El||n===wl||n===Tl||n===Al)if(r=t.get("WEBGL_compressed_texture_astc"),r!==null){if(n===pl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_4x4_KHR:r.COMPRESSED_RGBA_ASTC_4x4_KHR;if(n===ml)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_5x4_KHR:r.COMPRESSED_RGBA_ASTC_5x4_KHR;if(n===gl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_5x5_KHR:r.COMPRESSED_RGBA_ASTC_5x5_KHR;if(n===xl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_6x5_KHR:r.COMPRESSED_RGBA_ASTC_6x5_KHR;if(n===_l)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR:r.COMPRESSED_RGBA_ASTC_6x6_KHR;if(n===yl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_8x5_KHR:r.COMPRESSED_RGBA_ASTC_8x5_KHR;if(n===vl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_8x6_KHR:r.COMPRESSED_RGBA_ASTC_8x6_KHR;if(n===bl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_8x8_KHR:r.COMPRESSED_RGBA_ASTC_8x8_KHR;if(n===Ml)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x5_KHR:r.COMPRESSED_RGBA_ASTC_10x5_KHR;if(n===Sl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x6_KHR:r.COMPRESSED_RGBA_ASTC_10x6_KHR;if(n===El)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x8_KHR:r.COMPRESSED_RGBA_ASTC_10x8_KHR;if(n===wl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x10_KHR:r.COMPRESSED_RGBA_ASTC_10x10_KHR;if(n===Tl)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_12x10_KHR:r.COMPRESSED_RGBA_ASTC_12x10_KHR;if(n===Al)return a===Ae?r.COMPRESSED_SRGB8_ALPHA8_ASTC_12x12_KHR:r.COMPRESSED_RGBA_ASTC_12x12_KHR}else return null;if(n===Rl||n===Cl||n===Pl)if(r=t.get("EXT_texture_compression_bptc"),r!==null){if(n===Rl)return a===Ae?r.COMPRESSED_SRGB_ALPHA_BPTC_UNORM_EXT:r.COMPRESSED_RGBA_BPTC_UNORM_EXT;if(n===Cl)return r.COMPRESSED_RGB_BPTC_SIGNED_FLOAT_EXT;if(n===Pl)return r.COMPRESSED_RGB_BPTC_UNSIGNED_FLOAT_EXT}else return null;if(n===Il||n===Ll||n===Da||n===zl)if(r=t.get("EXT_texture_compression_rgtc"),r!==null){if(n===Il)return r.COMPRESSED_RED_RGTC1_EXT;if(n===Ll)return r.COMPRESSED_SIGNED_RED_RGTC1_EXT;if(n===Da)return r.COMPRESSED_RED_GREEN_RGTC2_EXT;if(n===zl)return r.COMPRESSED_SIGNED_RED_GREEN_RGTC2_EXT}else return null;return n===Fr?i.UNSIGNED_INT_24_8:i[n]!==void 0?i[n]:null}return{convert:e}}var T_=`
void main() {

	gl_Position = vec4( position, 1.0 );

}`,A_=`
uniform sampler2DArray depthColor;
uniform float depthWidth;
uniform float depthHeight;

void main() {

	vec2 coord = vec2( gl_FragCoord.x / depthWidth, gl_FragCoord.y / depthHeight );

	if ( coord.x >= 1.0 ) {

		gl_FragDepth = texture( depthColor, vec3( coord.x - 1.0, coord.y, 1 ) ).r;

	} else {

		gl_FragDepth = texture( depthColor, vec3( coord.x, coord.y, 0 ) ).r;

	}

}`,Ih=class{constructor(){this.texture=null,this.mesh=null,this.depthNear=0,this.depthFar=0}init(t,e){if(this.texture===null){let n=new _a(t.texture);(t.depthNear!==e.depthNear||t.depthFar!==e.depthFar)&&(this.depthNear=t.depthNear,this.depthFar=t.depthFar),this.texture=n}}getMesh(t){if(this.texture!==null&&this.mesh===null){let e=t.cameras[0].viewport,n=new Vn({vertexShader:T_,fragmentShader:A_,uniforms:{depthColor:{value:this.texture},depthWidth:{value:e.z},depthHeight:{value:e.w}}});this.mesh=new kt(new Hs(20,20),n)}return this.mesh}reset(){this.texture=null,this.mesh=null}getDepthTexture(){return this.texture}},Lh=class extends ci{constructor(t,e){super();let n=this,s=null,r=1,a=null,l="local-floor",o=1,c=null,h=null,f=null,d=null,p=null,x=null,M=typeof XRWebGLBinding<"u",m=new Ih,u={},b=e.getContextAttributes(),A=null,v=null,S=[],E=[],R=new Xt,g=null,w=null,T=new Je;T.viewport=new ke;let C=new Je;C.viewport=new ke;let D=[T,C],V=new qo,U=null,z=null;this.cameraAutoUpdate=!0,this.enabled=!1,this.isPresenting=!1,this.getController=function(J){let et=S[J];return et===void 0&&(et=new Rr,S[J]=et),et.getTargetRaySpace()},this.getControllerGrip=function(J){let et=S[J];return et===void 0&&(et=new Rr,S[J]=et),et.getGripSpace()},this.getHand=function(J){let et=S[J];return et===void 0&&(et=new Rr,S[J]=et),et.getHandSpace()};function q(J){let et=E.indexOf(J.inputSource);if(et===-1)return;let pt=S[et];pt!==void 0&&(pt.update(J.inputSource,J.frame,c||a),pt.dispatchEvent({type:J.type,data:J.inputSource}))}function N(){s.removeEventListener("select",q),s.removeEventListener("selectstart",q),s.removeEventListener("selectend",q),s.removeEventListener("squeeze",q),s.removeEventListener("squeezestart",q),s.removeEventListener("squeezeend",q),s.removeEventListener("end",N),s.removeEventListener("inputsourceschange",G);for(let J=0;J<S.length;J++){let et=E[J];et!==null&&(E[J]=null,S[J].disconnect(et))}U=null,z=null,m.reset();for(let J in u)delete u[J];if(t.setRenderTarget(A),p=null,d=null,f=null,s=null,v=null,gt.stop(),n.isPresenting=!1,t.setPixelRatio(g),t.setSize(R.width,R.height,!1),w!==null){let J=w.camera;J.fov=w.fov,J.zoom=w.zoom,J.updateProjectionMatrix(),w=null}n.dispatchEvent({type:"sessionend"})}this.setFramebufferScaleFactor=function(J){r=J,n.isPresenting===!0&&Zt("WebXRManager: Cannot change framebuffer scale while presenting.")},this.setReferenceSpaceType=function(J){l=J,n.isPresenting===!0&&Zt("WebXRManager: Cannot change reference space type while presenting.")},this.getReferenceSpace=function(){return c||a},this.setReferenceSpace=function(J){c=J},this.getBaseLayer=function(){return d!==null?d:p},this.getBinding=function(){return f===null&&M&&(f=new XRWebGLBinding(s,e)),f},this.getFrame=function(){return x},this.getSession=function(){return s},this.setSession=async function(J){if(s=J,s!==null){if(A=t.getRenderTarget(),s.addEventListener("select",q),s.addEventListener("selectstart",q),s.addEventListener("selectend",q),s.addEventListener("squeeze",q),s.addEventListener("squeezestart",q),s.addEventListener("squeezeend",q),s.addEventListener("end",N),s.addEventListener("inputsourceschange",G),b.xrCompatible!==!0&&await e.makeXRCompatible(),g=t.getPixelRatio(),t.getSize(R),M&&"createProjectionLayer"in XRWebGLBinding.prototype){let pt=null,At=null,Mt=null;b.depth&&(Mt=b.stencil?e.DEPTH24_STENCIL8:e.DEPTH_COMPONENT24,pt=b.stencil?Ss:Ei,At=b.stencil?Fr:di);let qt={colorFormat:e.RGBA8,depthFormat:Mt,scaleFactor:r};f=this.getBinding(),d=f.createProjectionLayer(qt),s.updateRenderState({layers:[d]}),t.setPixelRatio(1),t.setSize(d.textureWidth,d.textureHeight,!1),v=new In(d.textureWidth,d.textureHeight,{format:$n,type:Dn,depthTexture:new ps(d.textureWidth,d.textureHeight,At,void 0,void 0,void 0,void 0,void 0,void 0,pt),stencilBuffer:b.stencil,colorSpace:t.outputColorSpace,samples:b.antialias?4:0,resolveDepthBuffer:d.ignoreDepthValues===!1,resolveStencilBuffer:d.ignoreDepthValues===!1,storeMultisampledDepthBuffer:d.ignoreDepthValues===!1,storeMultisampledStencilBuffer:d.ignoreDepthValues===!1})}else{let pt={antialias:b.antialias,alpha:!0,depth:b.depth,stencil:b.stencil,framebufferScaleFactor:r};p=new XRWebGLLayer(s,e,pt),s.updateRenderState({baseLayer:p}),t.setPixelRatio(1),t.setSize(p.framebufferWidth,p.framebufferHeight,!1),v=new In(p.framebufferWidth,p.framebufferHeight,{format:$n,type:Dn,colorSpace:t.outputColorSpace,stencilBuffer:b.stencil,resolveDepthBuffer:p.ignoreDepthValues===!1,resolveStencilBuffer:p.ignoreDepthValues===!1,storeMultisampledDepthBuffer:p.ignoreDepthValues===!1,storeMultisampledStencilBuffer:p.ignoreDepthValues===!1})}v.isXRRenderTarget=!0,this.setFoveation(o),c=null,a=await s.requestReferenceSpace(l),gt.setContext(s),gt.start(),n.isPresenting=!0,n.dispatchEvent({type:"sessionstart"})}},this.getEnvironmentBlendMode=function(){if(s!==null)return s.environmentBlendMode},this.getDepthTexture=function(){return m.getDepthTexture()};function G(J){for(let et=0;et<J.removed.length;et++){let pt=J.removed[et],At=E.indexOf(pt);At>=0&&(E[At]=null,S[At].disconnect(pt))}for(let et=0;et<J.added.length;et++){let pt=J.added[et],At=E.indexOf(pt);if(At===-1){for(let qt=0;qt<S.length;qt++)if(qt>=E.length){E.push(pt),At=qt;break}else if(E[qt]===null){E[qt]=pt,At=qt;break}if(At===-1)break}let Mt=S[At];Mt&&Mt.connect(pt)}}let X=new F,K=new F;function nt(J,et,pt){X.setFromMatrixPosition(et.matrixWorld),K.setFromMatrixPosition(pt.matrixWorld);let At=X.distanceTo(K),Mt=et.projectionMatrix.elements,qt=pt.projectionMatrix.elements,ve=Mt[14]/(Mt[10]-1),Jt=Mt[14]/(Mt[10]+1),te=(Mt[9]+1)/Mt[5],ne=(Mt[9]-1)/Mt[5],jt=(Mt[8]-1)/Mt[0],xe=(qt[8]+1)/qt[0],ze=ve*jt,Ie=ve*xe,pe=At/(-jt+xe),_e=pe*-jt;if(et.matrixWorld.decompose(J.position,J.quaternion,J.scale),J.translateX(_e),J.translateZ(pe),J.matrixWorld.compose(J.position,J.quaternion,J.scale),J.matrixWorldInverse.copy(J.matrixWorld).invert(),Mt[10]===-1)J.projectionMatrix.copy(et.projectionMatrix),J.projectionMatrixInverse.copy(et.projectionMatrixInverse);else{let Y=ve+pe,Xe=Jt+pe,ye=ze-_e,L=Ie+(At-_e),y=te*Jt/Xe*Y,$=ne*Jt/Xe*Y;J.projectionMatrix.makePerspective(ye,L,y,$,Y,Xe),J.projectionMatrixInverse.copy(J.projectionMatrix).invert()}}function tt(J,et){et===null?J.matrixWorld.copy(J.matrix):J.matrixWorld.multiplyMatrices(et.matrixWorld,J.matrix),J.matrixWorldInverse.copy(J.matrixWorld).invert()}this.updateCamera=function(J){if(s===null)return;let et=J.near,pt=J.far;m.texture!==null&&(m.depthNear>0&&(et=m.depthNear),m.depthFar>0&&(pt=m.depthFar)),V.near=C.near=T.near=et,V.far=C.far=T.far=pt,(U!==V.near||z!==V.far)&&(s.updateRenderState({depthNear:V.near,depthFar:V.far}),U=V.near,z=V.far),V.layers.mask=J.layers.mask|6,T.layers.mask=V.layers.mask&-5,C.layers.mask=V.layers.mask&-3;let At=J.parent,Mt=V.cameras;tt(V,At);for(let qt=0;qt<Mt.length;qt++)tt(Mt[qt],At);Mt.length===2?nt(V,T,C):V.projectionMatrix.copy(T.projectionMatrix),w===null&&J.isPerspectiveCamera&&(w={camera:J,fov:J.fov,zoom:J.zoom}),lt(J,V,At)};function lt(J,et,pt){pt===null?J.matrix.copy(et.matrixWorld):(J.matrix.copy(pt.matrixWorld),J.matrix.invert(),J.matrix.multiply(et.matrixWorld)),J.matrix.decompose(J.position,J.quaternion,J.scale),J.updateMatrixWorld(!0),J.projectionMatrix.copy(et.projectionMatrix),J.projectionMatrixInverse.copy(et.projectionMatrixInverse),J.isPerspectiveCamera&&(J.fov=wr*2*Math.atan(1/J.projectionMatrix.elements[5]),J.zoom=1)}this.getCamera=function(){return V},this.getFoveation=function(){if(!(d===null&&p===null))return o},this.setFoveation=function(J){o=J,d!==null&&(d.fixedFoveation=J),p!==null&&p.fixedFoveation!==void 0&&(p.fixedFoveation=J)},this.hasDepthSensing=function(){return m.texture!==null},this.getDepthSensingMesh=function(){return m.getMesh(V)},this.getCameraTexture=function(J){return u[J]};let zt=null;function Lt(J,et){if(h=et.getViewerPose(c||a),x=et,h!==null){let pt=h.views;p!==null&&(t.setRenderTargetFramebuffer(v,p.framebuffer),t.setRenderTarget(v));let At=!1;pt.length!==V.cameras.length&&(V.cameras.length=0,At=!0);for(let Jt=0;Jt<pt.length;Jt++){let te=pt[Jt],ne=null;if(p!==null)ne=p.getViewport(te);else{let xe=f.getViewSubImage(d,te);ne=xe.viewport,Jt===0&&(t.setRenderTargetTextures(v,xe.colorTexture,xe.depthStencilTexture),t.setRenderTarget(v))}let jt=D[Jt];jt===void 0&&(jt=new Je,jt.layers.enable(Jt),jt.viewport=new ke,D[Jt]=jt),jt.matrix.fromArray(te.transform.matrix),jt.matrix.decompose(jt.position,jt.quaternion,jt.scale),jt.projectionMatrix.fromArray(te.projectionMatrix),jt.projectionMatrixInverse.copy(jt.projectionMatrix).invert(),jt.viewport.set(ne.x,ne.y,ne.width,ne.height),Jt===0&&(V.matrix.copy(jt.matrix),V.matrix.decompose(V.position,V.quaternion,V.scale)),At===!0&&V.cameras.push(jt)}let Mt=s.enabledFeatures;if(Mt&&Mt.includes("depth-sensing")&&s.depthUsage=="gpu-optimized"&&M){f=n.getBinding();let Jt=f.getDepthInformation(pt[0]);Jt&&Jt.isValid&&Jt.texture&&m.init(Jt,s.renderState)}if(Mt&&Mt.includes("camera-access")&&M){t.state.unbindTexture(),f=n.getBinding();for(let Jt=0;Jt<pt.length;Jt++){let te=pt[Jt].camera;if(te){let ne=u[te];ne||(ne=new _a,u[te]=ne);let jt=f.getCameraImage(te);ne.sourceTexture=jt}}}}for(let pt=0;pt<S.length;pt++){let At=E[pt],Mt=S[pt];At!==null&&Mt!==void 0&&Mt.update(At,et,c||a)}zt&&zt(J,et),et.detectedPlanes&&n.dispatchEvent({type:"planesdetected",data:et}),x=null}let gt=new Od;gt.setAnimationLoop(Lt),this.setAnimationLoop=function(J){zt=J},this.dispose=function(){}}},R_=new ge,Wd=new Qt;Wd.set(-1,0,0,0,1,0,0,0,1);function C_(i,t){function e(m,u){m.matrixAutoUpdate===!0&&m.updateMatrix(),u.value.copy(m.matrix)}function n(m,u){u.color.getRGB(m.fogColor.value,ch(i)),u.isFog?(m.fogNear.value=u.near,m.fogFar.value=u.far):u.isFogExp2&&(m.fogDensity.value=u.density)}function s(m,u,b,A,v){u.isNodeMaterial?u.uniformsNeedUpdate=!1:u.isMeshBasicMaterial?r(m,u):u.isMeshLambertMaterial?(r(m,u),u.envMap&&(m.envMapIntensity.value=u.envMapIntensity)):u.isMeshToonMaterial?(r(m,u),f(m,u)):u.isMeshPhongMaterial?(r(m,u),h(m,u),u.envMap&&(m.envMapIntensity.value=u.envMapIntensity)):u.isMeshStandardMaterial?(r(m,u),d(m,u),u.isMeshPhysicalMaterial&&p(m,u,v)):u.isMeshMatcapMaterial?(r(m,u),x(m,u)):u.isMeshDepthMaterial?r(m,u):u.isMeshDistanceMaterial?(r(m,u),M(m,u)):u.isMeshNormalMaterial?r(m,u):u.isLineBasicMaterial?(a(m,u),u.isLineDashedMaterial&&l(m,u)):u.isPointsMaterial?o(m,u,b,A):u.isSpriteMaterial?c(m,u):u.isShadowMaterial?(m.color.value.copy(u.color),m.opacity.value=u.opacity):u.isShaderMaterial&&(u.uniformsNeedUpdate=!1)}function r(m,u){m.opacity.value=u.opacity,u.color&&m.diffuse.value.copy(u.color),u.emissive&&m.emissive.value.copy(u.emissive).multiplyScalar(u.emissiveIntensity),u.map&&(m.map.value=u.map,e(u.map,m.mapTransform)),u.alphaMap&&(m.alphaMap.value=u.alphaMap,e(u.alphaMap,m.alphaMapTransform)),u.bumpMap&&(m.bumpMap.value=u.bumpMap,e(u.bumpMap,m.bumpMapTransform),m.bumpScale.value=u.bumpScale,u.side===Tn&&(m.bumpScale.value*=-1)),u.normalMap&&(m.normalMap.value=u.normalMap,e(u.normalMap,m.normalMapTransform),m.normalScale.value.copy(u.normalScale),u.side===Tn&&m.normalScale.value.negate()),u.displacementMap&&(m.displacementMap.value=u.displacementMap,e(u.displacementMap,m.displacementMapTransform),m.displacementScale.value=u.displacementScale,m.displacementBias.value=u.displacementBias),u.emissiveMap&&(m.emissiveMap.value=u.emissiveMap,e(u.emissiveMap,m.emissiveMapTransform)),u.specularMap&&(m.specularMap.value=u.specularMap,e(u.specularMap,m.specularMapTransform)),u.alphaTest>0&&(m.alphaTest.value=u.alphaTest);let b=t.get(u),A=b.envMap,v=b.envMapRotation;A&&(m.envMap.value=A,m.envMapRotation.value.setFromMatrix4(R_.makeRotationFromEuler(v)).transpose(),A.isCubeTexture&&A.isRenderTargetTexture===!1&&m.envMapRotation.value.premultiply(Wd),m.reflectivity.value=u.reflectivity,m.ior.value=u.ior,m.refractionRatio.value=u.refractionRatio),u.lightMap&&(m.lightMap.value=u.lightMap,m.lightMapIntensity.value=u.lightMapIntensity,e(u.lightMap,m.lightMapTransform)),u.aoMap&&(m.aoMap.value=u.aoMap,m.aoMapIntensity.value=u.aoMapIntensity,e(u.aoMap,m.aoMapTransform))}function a(m,u){m.diffuse.value.copy(u.color),m.opacity.value=u.opacity,u.map&&(m.map.value=u.map,e(u.map,m.mapTransform))}function l(m,u){m.dashSize.value=u.dashSize,m.totalSize.value=u.dashSize+u.gapSize,m.scale.value=u.scale}function o(m,u,b,A){m.diffuse.value.copy(u.color),m.opacity.value=u.opacity,m.size.value=u.size*b,m.scale.value=A*.5,u.map&&(m.map.value=u.map,e(u.map,m.uvTransform)),u.alphaMap&&(m.alphaMap.value=u.alphaMap,e(u.alphaMap,m.alphaMapTransform)),u.alphaTest>0&&(m.alphaTest.value=u.alphaTest)}function c(m,u){m.diffuse.value.copy(u.color),m.opacity.value=u.opacity,m.rotation.value=u.rotation,u.map&&(m.map.value=u.map,e(u.map,m.mapTransform)),u.alphaMap&&(m.alphaMap.value=u.alphaMap,e(u.alphaMap,m.alphaMapTransform)),u.alphaTest>0&&(m.alphaTest.value=u.alphaTest)}function h(m,u){m.specular.value.copy(u.specular),m.shininess.value=Math.max(u.shininess,1e-4)}function f(m,u){u.gradientMap&&(m.gradientMap.value=u.gradientMap)}function d(m,u){m.metalness.value=u.metalness,u.metalnessMap&&(m.metalnessMap.value=u.metalnessMap,e(u.metalnessMap,m.metalnessMapTransform)),m.roughness.value=u.roughness,u.roughnessMap&&(m.roughnessMap.value=u.roughnessMap,e(u.roughnessMap,m.roughnessMapTransform)),u.envMap&&(m.envMapIntensity.value=u.envMapIntensity)}function p(m,u,b){m.ior.value=u.ior,u.sheen>0&&(m.sheenColor.value.copy(u.sheenColor).multiplyScalar(u.sheen),m.sheenRoughness.value=u.sheenRoughness,u.sheenColorMap&&(m.sheenColorMap.value=u.sheenColorMap,e(u.sheenColorMap,m.sheenColorMapTransform)),u.sheenRoughnessMap&&(m.sheenRoughnessMap.value=u.sheenRoughnessMap,e(u.sheenRoughnessMap,m.sheenRoughnessMapTransform))),u.clearcoat>0&&(m.clearcoat.value=u.clearcoat,m.clearcoatRoughness.value=u.clearcoatRoughness,u.clearcoatMap&&(m.clearcoatMap.value=u.clearcoatMap,e(u.clearcoatMap,m.clearcoatMapTransform)),u.clearcoatRoughnessMap&&(m.clearcoatRoughnessMap.value=u.clearcoatRoughnessMap,e(u.clearcoatRoughnessMap,m.clearcoatRoughnessMapTransform)),u.clearcoatNormalMap&&(m.clearcoatNormalMap.value=u.clearcoatNormalMap,e(u.clearcoatNormalMap,m.clearcoatNormalMapTransform),m.clearcoatNormalScale.value.copy(u.clearcoatNormalScale),u.side===Tn&&m.clearcoatNormalScale.value.negate())),u.dispersion>0&&(m.dispersion.value=u.dispersion),u.retroreflectivity>0&&(m.retroreflectivity.value=u.retroreflectivity),u.iridescence>0&&(m.iridescence.value=u.iridescence,m.iridescenceIOR.value=u.iridescenceIOR,m.iridescenceThicknessMinimum.value=u.iridescenceThicknessRange[0],m.iridescenceThicknessMaximum.value=u.iridescenceThicknessRange[1],u.iridescenceMap&&(m.iridescenceMap.value=u.iridescenceMap,e(u.iridescenceMap,m.iridescenceMapTransform)),u.iridescenceThicknessMap&&(m.iridescenceThicknessMap.value=u.iridescenceThicknessMap,e(u.iridescenceThicknessMap,m.iridescenceThicknessMapTransform))),u.transmission>0&&(m.transmission.value=u.transmission,m.transmissionSamplerMap.value=b.texture,m.transmissionSamplerSize.value.set(b.width,b.height),u.transmissionMap&&(m.transmissionMap.value=u.transmissionMap,e(u.transmissionMap,m.transmissionMapTransform)),m.thickness.value=u.thickness,u.thicknessMap&&(m.thicknessMap.value=u.thicknessMap,e(u.thicknessMap,m.thicknessMapTransform)),m.attenuationDistance.value=u.attenuationDistance,m.attenuationColor.value.copy(u.attenuationColor)),u.anisotropy>0&&(m.anisotropyVector.value.set(u.anisotropy*Math.cos(u.anisotropyRotation),u.anisotropy*Math.sin(u.anisotropyRotation)),u.anisotropyMap&&(m.anisotropyMap.value=u.anisotropyMap,e(u.anisotropyMap,m.anisotropyMapTransform))),m.specularIntensity.value=u.specularIntensity,m.specularColor.value.copy(u.specularColor),u.specularColorMap&&(m.specularColorMap.value=u.specularColorMap,e(u.specularColorMap,m.specularColorMapTransform)),u.specularIntensityMap&&(m.specularIntensityMap.value=u.specularIntensityMap,e(u.specularIntensityMap,m.specularIntensityMapTransform))}function x(m,u){u.matcap&&(m.matcap.value=u.matcap)}function M(m,u){let b=t.get(u).light;m.referencePosition.value.setFromMatrixPosition(b.matrixWorld),m.nearDistance.value=b.shadow.camera.near,m.farDistance.value=b.shadow.camera.far}return{refreshFogUniforms:n,refreshMaterialUniforms:s}}function P_(i,t,e,n){let s={},r={},a=[],l=i.getParameter(i.MAX_UNIFORM_BUFFER_BINDINGS);function o(v,S){let E=S.program;n.uniformBlockBinding(v,E)}function c(v,S){let E=s[v.id];E===void 0&&(m(v),E=h(v),s[v.id]=E,v.addEventListener("dispose",b));let R=S.program;n.updateUBOMapping(v,R);let g=t.render.frame;r[v.id]!==g&&(d(v),r[v.id]=g)}function h(v){let S=f();v.__bindingPointIndex=S;let E=i.createBuffer(),R=v.__size,g=v.usage;return i.bindBuffer(i.UNIFORM_BUFFER,E),i.bufferData(i.UNIFORM_BUFFER,R,g),i.bindBuffer(i.UNIFORM_BUFFER,null),i.bindBufferBase(i.UNIFORM_BUFFER,S,E),E}function f(){for(let v=0;v<l;v++)if(a.indexOf(v)===-1)return a.push(v),v;return Kt("WebGLRenderer: Maximum number of simultaneously usable uniforms groups reached."),0}function d(v){let S=s[v.id],E=v.uniforms,R=v.__cache;i.bindBuffer(i.UNIFORM_BUFFER,S);for(let g=0,w=E.length;g<w;g++){let T=E[g];if(Array.isArray(T))for(let C=0,D=T.length;C<D;C++)p(T[C],g,C,R);else p(T,g,0,R)}i.bindBuffer(i.UNIFORM_BUFFER,null)}function p(v,S,E,R){if(M(v,S,E,R)===!0){let g=v.__offset,w=v.value;if(Array.isArray(w)){let T=0;for(let C=0;C<w.length;C++){let D=w[C],V=u(D);x(D,v.__data,T),typeof D!="number"&&typeof D!="boolean"&&!D.isMatrix3&&!ArrayBuffer.isView(D)&&(T+=V.storage/Float32Array.BYTES_PER_ELEMENT)}}else x(w,v.__data,0);i.bufferSubData(i.UNIFORM_BUFFER,g,v.__data)}}function x(v,S,E){typeof v=="number"||typeof v=="boolean"?S[0]=v:v.isMatrix3?(S[0]=v.elements[0],S[1]=v.elements[1],S[2]=v.elements[2],S[3]=0,S[4]=v.elements[3],S[5]=v.elements[4],S[6]=v.elements[5],S[7]=0,S[8]=v.elements[6],S[9]=v.elements[7],S[10]=v.elements[8],S[11]=0):ArrayBuffer.isView(v)?S.set(new v.constructor(v.buffer,v.byteOffset,S.length)):v.toArray(S,E)}function M(v,S,E,R){let g=v.value,w=S+"_"+E;if(R[w]===void 0)return typeof g=="number"||typeof g=="boolean"?R[w]=g:ArrayBuffer.isView(g)?R[w]=g.slice():R[w]=g.clone(),!0;{let T=R[w];if(typeof g=="number"||typeof g=="boolean"){if(T!==g)return R[w]=g,!0}else{if(ArrayBuffer.isView(g))return!0;if(T.equals(g)===!1)return T.copy(g),!0}}return!1}function m(v){let S=v.uniforms,E=0,R=16;for(let w=0,T=S.length;w<T;w++){let C=Array.isArray(S[w])?S[w]:[S[w]];for(let D=0,V=C.length;D<V;D++){let U=C[D],z=Array.isArray(U.value)?U.value:[U.value];for(let q=0,N=z.length;q<N;q++){let G=z[q],X=u(G),K=E%R,nt=K%X.boundary,tt=K+nt;E+=nt,tt!==0&&R-tt<X.storage&&(E+=R-tt),U.__data=new Float32Array(X.storage/Float32Array.BYTES_PER_ELEMENT),U.__offset=E,E+=X.storage}}}let g=E%R;return g>0&&(E+=R-g),v.__size=E,v.__cache={},this}function u(v){let S={boundary:0,storage:0};return typeof v=="number"||typeof v=="boolean"?(S.boundary=4,S.storage=4):v.isVector2?(S.boundary=8,S.storage=8):v.isVector3||v.isColor?(S.boundary=16,S.storage=12):v.isVector4?(S.boundary=16,S.storage=16):v.isMatrix3?(S.boundary=48,S.storage=48):v.isMatrix4?(S.boundary=64,S.storage=64):v.isTexture?Zt("WebGLRenderer: Texture samplers can not be part of an uniforms group."):ArrayBuffer.isView(v)?(S.boundary=16,S.storage=v.byteLength):Zt("WebGLRenderer: Unsupported uniform value type.",v),S}function b(v){let S=v.target;S.removeEventListener("dispose",b);let E=a.indexOf(S.__bindingPointIndex);a.splice(E,1),i.deleteBuffer(s[S.id]),delete s[S.id],delete r[S.id]}function A(){for(let v in s)i.deleteBuffer(s[v]);a=[],s={},r={}}return{bind:o,update:c,dispose:A}}var I_=new Uint16Array([12469,15057,12620,14925,13266,14620,13807,14376,14323,13990,14545,13625,14713,13328,14840,12882,14931,12528,14996,12233,15039,11829,15066,11525,15080,11295,15085,10976,15082,10705,15073,10495,13880,14564,13898,14542,13977,14430,14158,14124,14393,13732,14556,13410,14702,12996,14814,12596,14891,12291,14937,11834,14957,11489,14958,11194,14943,10803,14921,10506,14893,10278,14858,9960,14484,14039,14487,14025,14499,13941,14524,13740,14574,13468,14654,13106,14743,12678,14818,12344,14867,11893,14889,11509,14893,11180,14881,10751,14852,10428,14812,10128,14765,9754,14712,9466,14764,13480,14764,13475,14766,13440,14766,13347,14769,13070,14786,12713,14816,12387,14844,11957,14860,11549,14868,11215,14855,10751,14825,10403,14782,10044,14729,9651,14666,9352,14599,9029,14967,12835,14966,12831,14963,12804,14954,12723,14936,12564,14917,12347,14900,11958,14886,11569,14878,11247,14859,10765,14828,10401,14784,10011,14727,9600,14660,9289,14586,8893,14508,8533,15111,12234,15110,12234,15104,12216,15092,12156,15067,12010,15028,11776,14981,11500,14942,11205,14902,10752,14861,10393,14812,9991,14752,9570,14682,9252,14603,8808,14519,8445,14431,8145,15209,11449,15208,11451,15202,11451,15190,11438,15163,11384,15117,11274,15055,10979,14994,10648,14932,10343,14871,9936,14803,9532,14729,9218,14645,8742,14556,8381,14461,8020,14365,7603,15273,10603,15272,10607,15267,10619,15256,10631,15231,10614,15182,10535,15118,10389,15042,10167,14963,9787,14883,9447,14800,9115,14710,8665,14615,8318,14514,7911,14411,7507,14279,7198,15314,9675,15313,9683,15309,9712,15298,9759,15277,9797,15229,9773,15166,9668,15084,9487,14995,9274,14898,8910,14800,8539,14697,8234,14590,7790,14479,7409,14367,7067,14178,6621,15337,8619,15337,8631,15333,8677,15325,8769,15305,8871,15264,8940,15202,8909,15119,8775,15022,8565,14916,8328,14804,8009,14688,7614,14569,7287,14448,6888,14321,6483,14088,6171,15350,7402,15350,7419,15347,7480,15340,7613,15322,7804,15287,7973,15229,8057,15148,8012,15046,7846,14933,7611,14810,7357,14682,7069,14552,6656,14421,6316,14251,5948,14007,5528,15356,5942,15356,5977,15353,6119,15348,6294,15332,6551,15302,6824,15249,7044,15171,7122,15070,7050,14949,6861,14818,6611,14679,6349,14538,6067,14398,5651,14189,5311,13935,4958,15359,4123,15359,4153,15356,4296,15353,4646,15338,5160,15311,5508,15263,5829,15188,6042,15088,6094,14966,6001,14826,5796,14678,5543,14527,5287,14377,4985,14133,4586,13869,4257,15360,1563,15360,1642,15358,2076,15354,2636,15341,3350,15317,4019,15273,4429,15203,4732,15105,4911,14981,4932,14836,4818,14679,4621,14517,4386,14359,4156,14083,3795,13808,3437,15360,122,15360,137,15358,285,15355,636,15344,1274,15322,2177,15281,2765,15215,3223,15120,3451,14995,3569,14846,3567,14681,3466,14511,3305,14344,3121,14037,2800,13753,2467,15360,0,15360,1,15359,21,15355,89,15346,253,15325,479,15287,796,15225,1148,15133,1492,15008,1749,14856,1882,14685,1886,14506,1783,14324,1608,13996,1398,13702,1183]),Ci=null;function L_(){return Ci===null&&(Ci=new ga(I_,16,16,Es,fi),Ci.name="DFG_LUT",Ci.minFilter=mn,Ci.magFilter=mn,Ci.wrapS=Mi,Ci.wrapT=Mi,Ci.generateMipmaps=!1,Ci.needsUpdate=!0),Ci}var Vr=class{constructor(t={}){let{canvas:e=cd(),context:n=null,depth:s=!0,stencil:r=!1,alpha:a=!1,antialias:l=!1,premultipliedAlpha:o=!0,preserveDrawingBuffer:c=!1,powerPreference:h="default",failIfMajorPerformanceCaveat:f=!1,reversedDepthBuffer:d=!1,outputBufferType:p=Dn}=t;this.isWebGLRenderer=!0;let x;if(n!==null){if(typeof WebGLRenderingContext<"u"&&n instanceof WebGLRenderingContext)throw new Error("THREE.WebGLRenderer: WebGL 1 is not supported since r163.");x=n.getContextAttributes().alpha}else x=a;let M=p,m=new Set([il,nl,el]),u=new Set([Dn,di,Ur,Fr,jo,Qo]),b=new Uint32Array(4),A=new Int32Array(4),v=new F,S=null,E=null,R=[],g=[],w=null;this.domElement=e,this.debug={checkShaderErrors:!0,diagnostics:{keywords:!1},onShaderError:null},this.autoClear=!0,this.autoClearColor=!0,this.autoClearDepth=!0,this.autoClearStencil=!0,this.sortObjects=!0,this.clippingPlanes=[],this.localClippingEnabled=!1,this.toneMapping=ui,this.toneMappingExposure=1,this.transmissionResolutionScale=1;let T=this,C=!1,D=null,V=null,U=null,z=null;this._outputColorSpace=Ge;let q=0,N=0,G=null,X=-1,K=null,nt=new ke,tt=new ke,lt=null,zt=new $t(0),Lt=0,gt=e.width,J=e.height,et=1,pt=null,At=null,Mt=new ke(0,0,gt,J),qt=new ke(0,0,gt,J),ve=!1,Jt=new Pr,te=!1,ne=!1,jt=new ge,xe=new F,ze=new ke,Ie={background:null,fog:null,environment:null,overrideMaterial:null,isScene:!0},pe=!1;function _e(){return G===null?et:1}let Y=n;function Xe(_,P){return e.getContext(_,P)}let ye,L,y,$,Q,it,xt,wt,rt,ot,St,Bt,Pt,Et,Ht,Vt,Wt,W,Rt,ht,Tt,It,B;try{let _={alpha:!0,depth:s,stencil:r,antialias:l,premultipliedAlpha:o,preserveDrawingBuffer:c,powerPreference:h,failIfMajorPerformanceCaveat:f};if("setAttribute"in e&&e.setAttribute("data-engine",`three.js r${"186"}`),e.addEventListener("webglcontextlost",mt,!1),e.addEventListener("webglcontextrestored",vt,!1),e.addEventListener("webglcontextcreationerror",re,!1),Y===null){let P="webgl2";if(Y=Xe(P,_),Y===null)throw Xe(P)?new Error("THREE.WebGLRenderer: Error creating WebGL context with your selected attributes."):new Error("THREE.WebGLRenderer: Error creating WebGL context.")}at()}catch(_){throw e.removeEventListener("webglcontextlost",mt,!1),e.removeEventListener("webglcontextrestored",vt,!1),e.removeEventListener("webglcontextcreationerror",re,!1),Kt("WebGLRenderer: "+_.message),_}function at(){ye=new Bg(Y),ye.init(),Tt=new w_(Y,ye),L=new Cg(Y,ye,t,Tt),y=new S_(Y,ye),L.reversedDepthBuffer&&d&&y.buffers.depth.setReversed(!0),V=Y.createFramebuffer(),U=Y.createFramebuffer(),z=Y.createFramebuffer(),$=new Vg(Y),Q=new c_,it=new E_(Y,ye,y,Q,L,Tt,$),xt=new Og(T),wt=new Wp(Y),It=new Ag(Y,wt),rt=new kg(Y,wt,$,It),ot=new Wg(Y,rt,wt,It,$),W=new Gg(Y,L,it),Ht=new Pg(Q),St=new l_(T,xt,ye,L,It,Ht),Bt=new C_(T,Q),Pt=new u_,Et=new x_(ye),Wt=new Tg(T,xt,y,ot,x,o),Vt=new M_(T,ot,L),B=new P_(Y,$,L,y),Rt=new Rg(Y,ye,$),ht=new Hg(Y,ye,$),$.programs=St.programs,T.capabilities=L,T.extensions=ye,T.properties=Q,T.renderLists=Pt,T.shadowMap=Vt,T.state=y,T.info=$}M!==Dn&&(w=new qg(M,e.width,e.height,l,s,r));let ut=new Lh(T,Y);this.xr=ut,this.getContext=function(){return Y},this.getContextAttributes=function(){return Y.getContextAttributes()},this.forceContextLoss=function(){let _=ye.get("WEBGL_lose_context");_&&_.loseContext()},this.forceContextRestore=function(){let _=ye.get("WEBGL_lose_context");_&&_.restoreContext()},this.getPixelRatio=function(){return et},this.setPixelRatio=function(_){_!==void 0&&(et=_,this.setSize(gt,J,!1))},this.getSize=function(_){return _.set(gt,J)},this.setSize=function(_,P,H=!0){if(ut.isPresenting){Zt("WebGLRenderer: Can't change size while VR device is presenting.");return}gt=_,J=P,e.width=Math.floor(_*et),e.height=Math.floor(P*et),H===!0&&(e.style.width=_+"px",e.style.height=P+"px"),w!==null&&w.setSize(e.width,e.height),this.setViewport(0,0,_,P)},this.getDrawingBufferSize=function(_){return _.set(gt*et,J*et).floor()},this.setDrawingBufferSize=function(_,P,H){gt=_,J=P,et=H,e.width=Math.floor(_*H),e.height=Math.floor(P*H),this.setViewport(0,0,_,P)},this.setEffects=function(_){if(M===Dn){Kt("WebGLRenderer: setEffects() requires outputBufferType set to HalfFloatType or FloatType.");return}if(_){for(let P=0;P<_.length;P++)if(_[P].isOutputPass===!0){Zt("WebGLRenderer: OutputPass is not needed in setEffects(). Tone mapping and color space conversion are applied automatically.");break}}w.setEffects(_||[])},this.getCurrentViewport=function(_){return _.copy(nt)},this.getViewport=function(_){return _.copy(Mt)},this.setViewport=function(_,P,H,O){_.isVector4?Mt.set(_.x,_.y,_.z,_.w):Mt.set(_,P,H,O),y.viewport(nt.copy(Mt).multiplyScalar(et).round())},this.getScissor=function(_){return _.copy(qt)},this.setScissor=function(_,P,H,O){_.isVector4?qt.set(_.x,_.y,_.z,_.w):qt.set(_,P,H,O),y.scissor(tt.copy(qt).multiplyScalar(et).round())},this.getScissorTest=function(){return ve},this.setScissorTest=function(_){y.setScissorTest(ve=_)},this.setOpaqueSort=function(_){pt=_},this.setTransparentSort=function(_){At=_},this.getClearColor=function(_){return _.copy(Wt.getClearColor())},this.setClearColor=function(){Wt.setClearColor(...arguments)},this.getClearAlpha=function(){return Wt.getClearAlpha()},this.setClearAlpha=function(){Wt.setClearAlpha(...arguments)},this.clear=function(_=!0,P=!0,H=!0){let O=0;if(_){let k=!1;if(G!==null){let st=G.texture.format;k=m.has(st)}if(k){let st=G.texture.type,ct=u.has(st),_t=Wt.getClearColor(),yt=Wt.getClearAlpha(),Nt=_t.r,Yt=_t.g,ie=_t.b;ct?(b[0]=Nt,b[1]=Yt,b[2]=ie,b[3]=yt,Y.clearBufferuiv(Y.COLOR,0,b)):(A[0]=Nt,A[1]=Yt,A[2]=ie,A[3]=yt,Y.clearBufferiv(Y.COLOR,0,A))}else O|=Y.COLOR_BUFFER_BIT}P&&(O|=Y.DEPTH_BUFFER_BIT,this.state.buffers.depth.setMask(!0)),H&&(O|=Y.STENCIL_BUFFER_BIT,this.state.buffers.stencil.setMask(4294967295)),O!==0&&Y.clear(O)},this.clearColor=function(){this.clear(!0,!1,!1)},this.clearDepth=function(){this.clear(!1,!0,!1)},this.clearStencil=function(){this.clear(!1,!1,!0)},this.setNodesHandler=function(_){_.setRenderer(this),D=_},this.dispose=function(){e.removeEventListener("webglcontextlost",mt,!1),e.removeEventListener("webglcontextrestored",vt,!1),e.removeEventListener("webglcontextcreationerror",re,!1),Wt.dispose(),Pt.dispose(),Et.dispose(),Q.dispose(),xt.dispose(),ot.dispose(),It.dispose(),B.dispose(),St.dispose(),ut.dispose(),ut.removeEventListener("sessionstart",ns),ut.removeEventListener("sessionend",ir),Pn.stop()};function mt(_){_.preventDefault(),oh("WebGLRenderer: Context Lost."),C=!0}function vt(){oh("WebGLRenderer: Context Restored."),C=!1;let _=$.autoReset,P=Vt.enabled,H=Vt.autoUpdate,O=Vt.needsUpdate,k=Vt.type;at(),$.autoReset=_,Vt.enabled=P,Vt.autoUpdate=H,Vt.needsUpdate=O,Vt.type=k}function re(_){Kt("WebGLRenderer: A WebGL context could not be created. Reason: ",_.statusMessage)}function Ft(_){let P=_.target;P.removeEventListener("dispose",Ft),Ce(P)}function Ce(_){De(_),Q.remove(_)}function De(_){let P=Q.get(_).programs;P!==void 0&&(P.forEach(function(H){St.releaseProgram(H)}),_.isShaderMaterial&&St.releaseShaderCache(_))}this.renderBufferDirect=function(_,P,H,O,k,st){P===null&&(P=Ie);let ct=k.isMesh&&k.matrixWorld.determinantAffine()<0,_t=Z(_,P,H,O,k);y.setMaterial(O,ct);let yt=H.index,Nt=1;if(O.wireframe===!0){if(yt=rt.getWireframeAttribute(H),yt===void 0)return;Nt=2}let Yt=H.drawRange,ie=H.attributes.position,Ut=Yt.start*Nt,ue=(Yt.start+Yt.count)*Nt;st!==null&&(Ut=Math.max(Ut,st.start*Nt),ue=Math.min(ue,(st.start+st.count)*Nt)),yt!==null?(Ut=Math.max(Ut,0),ue=Math.min(ue,yt.count)):ie!=null&&(Ut=Math.max(Ut,0),ue=Math.min(ue,ie.count));let Oe=ue-Ut;if(Oe<0||Oe===1/0)return;It.setup(k,O,_t,H,yt);let Te,Se=Rt;if(yt!==null&&(Te=wt.get(yt),Se=ht,Se.setIndex(Te)),k.isMesh)O.wireframe===!0?(y.setLineWidth(O.wireframeLinewidth*_e()),Se.setMode(Y.LINES)):Se.setMode(Y.TRIANGLES);else if(k.isLine){let Ve=O.linewidth;Ve===void 0&&(Ve=1),y.setLineWidth(Ve*_e()),k.isLineSegments?Se.setMode(Y.LINES):k.isLineLoop?Se.setMode(Y.LINE_LOOP):Se.setMode(Y.LINE_STRIP)}else k.isPoints?Se.setMode(Y.POINTS):k.isSprite&&Se.setMode(Y.TRIANGLES);if(k.isBatchedMesh)if(ye.get("WEBGL_multi_draw"))Se.renderMultiDraw(k._multiDrawStarts,k._multiDrawCounts,k._multiDrawCount);else{let Ve=k._multiDrawStarts,ft=k._multiDrawCounts,Be=k._multiDrawCount,oe=yt?wt.get(yt).bytesPerElement:1,fn=Q.get(O).currentProgram.getUniforms();for(let Fn=0;Fn<Be;Fn++)fn.setValue(Y,"_gl_DrawID",Fn),Se.render(Ve[Fn]/oe,ft[Fn])}else if(k.isInstancedMesh)Se.renderInstances(Ut,Oe,k.count);else if(H.isInstancedBufferGeometry){let Ve=H._maxInstanceCount!==void 0?H._maxInstanceCount:1/0,ft=Math.min(H.instanceCount,Ve);Se.renderInstances(Ut,Oe,ft)}else Se.render(Ut,Oe)};function Ke(_,P,H,O){D!==null&&_.isNodeMaterial&&D.setObject(O,_),te===!0&&Ht.setState(_,H,!1),_.transparent===!0&&_.side===Ai&&_.forceSinglePass===!1?(_.side=Tn,_.needsUpdate=!0,Ls(_,P,O),_.side=vs,_.needsUpdate=!0,Ls(_,P,O),_.side=Ai):Ls(_,P,O)}this.compile=function(_,P,H=null){H===null&&(H=_),D!==null&&D.renderStart(_,P,H),E=Et.get(H),E.init(P),g.push(E),H.traverseVisible(function(k){k.isLight&&k.layers.test(P.layers)&&(E.pushLight(k),k.castShadow&&E.pushShadow(k))}),_!==H&&_.traverseVisible(function(k){k.isLight&&k.layers.test(P.layers)&&(E.pushLight(k),k.castShadow&&E.pushShadow(k))}),E.setupLights(),D!==null&&D.updateLights(E.state.lightsArray),ne=this.localClippingEnabled,te=Ht.init(this.clippingPlanes,ne),te===!0&&Ht.setGlobalState(this.clippingPlanes,P),D!==null&&Vt.render(E.state.shadowsArray,H,P);let O=new Set;return _.traverse(function(k){if(!(k.isMesh||k.isPoints||k.isLine||k.isSprite))return;let st=k.material;if(st)if(Array.isArray(st))for(let ct=0;ct<st.length;ct++){let _t=st[ct];Ke(_t,H,P,k),O.add(_t)}else Ke(st,H,P,k),O.add(st)}),E=g.pop(),D!==null&&D.renderEnd(),O},this.compileAsync=function(_,P,H=null){let O=this.compile(_,P,H);return new Promise(k=>{function st(){if(O.forEach(function(ct){let yt=Q.get(ct).currentProgram;(yt===void 0||yt.isReady())&&O.delete(ct)}),O.size===0){k(_);return}setTimeout(st,10)}ye.get("KHR_parallel_shader_compile")!==null?st():setTimeout(st,10)})};let sn=null;function Mn(_){sn&&sn(_)}function ns(){Pn.stop()}function ir(){Pn.start()}let Pn=new Od;Pn.setAnimationLoop(Mn),typeof self<"u"&&Pn.setContext(self),this.setAnimationLoop=function(_){sn=_,ut.setAnimationLoop(_),_===null?Pn.stop():Pn.start()},ut.addEventListener("sessionstart",ns),ut.addEventListener("sessionend",ir),this.render=function(_,P){if(P!==void 0&&P.isCamera!==!0){Kt("WebGLRenderer.render: camera is not an instance of THREE.Camera.");return}if(C===!0)return;D!==null&&D.renderStart(_,P);let H=ut.enabled===!0&&ut.isPresenting===!0,O=w!==null&&(G===null||H)&&w.begin(T,G);if(_.matrixWorldAutoUpdate===!0&&_.updateMatrixWorld(),P.parent===null&&P.matrixWorldAutoUpdate===!0&&P.updateMatrixWorld(),ut.enabled===!0&&ut.isPresenting===!0&&(w===null||w.isCompositing()===!1)&&(ut.cameraAutoUpdate===!0&&ut.updateCamera(P),P=ut.getCamera()),_.isScene===!0&&_.onBeforeRender(T,_,P,G),E=Et.get(_,g.length),E.init(P),E.state.textureUnits=it.getTextureUnits(),g.push(E),jt.multiplyMatrices(P.projectionMatrix,P.matrixWorldInverse),Jt.setFromProjectionMatrix(jt,li,P.reversedDepth),ne=this.localClippingEnabled,te=Ht.init(this.clippingPlanes,ne),S=Pt.get(_,R.length),S.init(),R.push(S),ut.enabled===!0&&ut.isPresenting===!0){let ct=T.xr.getDepthSensingMesh();ct!==null&&vi(ct,P,-1/0,T.sortObjects)}vi(_,P,0,T.sortObjects),S.finish(),D!==null&&D.updateLights(E.state.lightsArray),T.sortObjects===!0&&S.sort(pt,At),pe=ut.enabled===!1||ut.isPresenting===!1||ut.hasDepthSensing()===!1,pe&&Wt.addToRenderList(S,_),this.info.render.frame++,this.info.autoReset===!0&&this.info.reset(),te===!0&&Ht.beginShadows();let k=E.state.shadowsArray;if(Vt.render(k,_,P),te===!0&&Ht.endShadows(),(O&&w.hasRenderPass())===!1){let ct=S.opaque,_t=S.transmissive;if(E.setupLights(),P.isArrayCamera){let yt=P.cameras;if(_t.length>0)for(let Nt=0,Yt=yt.length;Nt<Yt;Nt++){let ie=yt[Nt];Ya(ct,_t,_,ie)}pe&&Wt.render(_);for(let Nt=0,Yt=yt.length;Nt<Yt;Nt++){let ie=yt[Nt];is(S,_,ie,ie.viewport)}}else _t.length>0&&Ya(ct,_t,_,P),pe&&Wt.render(_),is(S,_,P)}G!==null&&N===0&&(it.updateMultisampleRenderTarget(G),it.updateRenderTargetMipmap(G)),O&&w.end(T),_.isScene===!0&&_.onAfterRender(T,_,P),It.resetDefaultState(),X=-1,K=null,g.pop(),g.length>0?(E=g[g.length-1],it.setTextureUnits(E.state.textureUnits),te===!0&&Ht.setGlobalState(T.clippingPlanes,E.state.camera)):E=null,R.pop(),R.length>0?S=R[R.length-1]:S=null,D!==null&&D.renderEnd()};function vi(_,P,H,O){if(_.visible===!1)return;if(_.layers.test(P.layers)){if(_.isGroup)H=_.renderOrder;else if(_.isLOD)_.autoUpdate===!0&&_.update(P);else if(_.isLightProbeGrid)E.pushLightProbeGrid(_);else if(_.isLight)E.pushLight(_),_.castShadow&&E.pushShadow(_);else if(_.isSprite){if(!_.frustumCulled||_.intersectsFrustum(Jt)){O&&ze.setFromMatrixPosition(_.matrixWorld).applyMatrix4(jt);let ct=ot.update(_),_t=_.material;_t.visible&&S.push(_,ct,_t,H,ze.z,null,P)}}else if((_.isMesh||_.isLine||_.isPoints)&&(!_.frustumCulled||_.intersectsFrustum(Jt))){let ct=ot.update(_),_t=_.material;if(O&&(_.boundingSphere!==void 0?(_.boundingSphere===null&&_.computeBoundingSphere(),ze.copy(_.boundingSphere.center)):(ct.boundingSphere===null&&ct.computeBoundingSphere(),ze.copy(ct.boundingSphere.center)),ze.applyMatrix4(_.matrixWorld).applyMatrix4(jt)),Array.isArray(_t)){let yt=ct.groups;for(let Nt=0,Yt=yt.length;Nt<Yt;Nt++){let ie=yt[Nt],Ut=_t[ie.materialIndex];Ut&&Ut.visible&&S.push(_,ct,Ut,H,ze.z,ie,P)}}else _t.visible&&S.push(_,ct,_t,H,ze.z,null,P)}}let st=_.children;for(let ct=0,_t=st.length;ct<_t;ct++)vi(st[ct],P,H,O)}function is(_,P,H,O){let{opaque:k,transmissive:st,transparent:ct}=_;E.setupLightsView(H),te===!0&&Ht.setGlobalState(T.clippingPlanes,H),O&&y.viewport(nt.copy(O)),k.length>0&&Is(k,P,H),st.length>0&&Is(st,P,H),ct.length>0&&Is(ct,P,H),y.buffers.depth.setTest(!0),y.buffers.depth.setMask(!0),y.buffers.color.setMask(!0),y.setPolygonOffset(!1)}function Ya(_,P,H,O){if((H.isScene===!0?H.overrideMaterial:null)!==null)return;if(E.state.transmissionRenderTarget[O.id]===void 0){let Ut=ye.has("EXT_color_buffer_half_float")||ye.has("EXT_color_buffer_float");E.state.transmissionRenderTarget[O.id]=new In(1,1,{generateMipmaps:!0,type:Ut?fi:Dn,minFilter:Ms,samples:Math.max(4,L.samples),stencilBuffer:r,resolveDepthBuffer:!1,resolveStencilBuffer:!1,storeMultisampledDepthBuffer:!1,storeMultisampledStencilBuffer:!1,colorSpace:me.workingColorSpace})}let st=E.state.transmissionRenderTarget[O.id],ct=O.viewport||nt;st.setSize(ct.z*T.transmissionResolutionScale,ct.w*T.transmissionResolutionScale);let _t=T.getRenderTarget(),yt=T.getActiveCubeFace(),Nt=T.getActiveMipmapLevel();T.setRenderTarget(st),T.getClearColor(zt),Lt=T.getClearAlpha(),Lt<1&&T.setClearColor(16777215,.5),T.clear(),pe&&Wt.render(H);let Yt=T.toneMapping;T.toneMapping=ui;let ie=O.viewport;if(O.viewport!==void 0&&(O.viewport=void 0),E.setupLightsView(O),te===!0&&Ht.setGlobalState(T.clippingPlanes,O),Is(_,H,O),it.updateMultisampleRenderTarget(st),it.updateRenderTargetMipmap(st),ye.has("WEBGL_multisampled_render_to_texture")===!1){let Ut=!1;for(let ue=0,Oe=P.length;ue<Oe;ue++){let Te=P[ue],{object:Se,geometry:Ve,material:ft,group:Be}=Te;if(ft.side===Ai&&Se.layers.test(O.layers)){let oe=ft.side;ft.side=Tn,ft.needsUpdate=!0,Sn(Se,H,O,Ve,ft,Be),ft.side=oe,ft.needsUpdate=!0,Ut=!0}}Ut===!0&&(it.updateMultisampleRenderTarget(st),it.updateRenderTargetMipmap(st))}T.setRenderTarget(_t,yt,Nt),T.setClearColor(zt,Lt),ie!==void 0&&(O.viewport=ie),T.toneMapping=Yt}function Is(_,P,H){let O=P.isScene===!0?P.overrideMaterial:null;for(let k=0,st=_.length;k<st;k++){let ct=_[k],{object:_t,geometry:yt,group:Nt}=ct,Yt=ct.material;Yt.allowOverride===!0&&O!==null&&(Yt=O),_t.layers.test(H.layers)&&Sn(_t,P,H,yt,Yt,Nt)}}function Sn(_,P,H,O,k,st){D!==null&&k.isNodeMaterial&&D.setObject(_,k),_.onBeforeRender(T,P,H,O,k,st),_.modelViewMatrix.multiplyMatrices(H.matrixWorldInverse,_.matrixWorld),_.normalMatrix.getNormalMatrix(_.modelViewMatrix),k.onBeforeRender(T,P,H,O,_,st),k.transparent===!0&&k.side===Ai&&k.forceSinglePass===!1?(k.side=Tn,k.needsUpdate=!0,T.renderBufferDirect(H,P,O,k,_,st),k.side=vs,k.needsUpdate=!0,T.renderBufferDirect(H,P,O,k,_,st),k.side=Ai):T.renderBufferDirect(H,P,O,k,_,st),_.onAfterRender(T,P,H,O,k,st)}function Ls(_,P,H){P.isScene!==!0&&(P=Ie);let O=Q.get(_),k=E.state.lights,st=E.state.shadowsArray,ct=k.state.version,_t=St.getParameters(_,k.state,st,P,H,E.state.lightProbeGridArray),yt=St.getProgramCacheKey(_t),Nt=O.programs;O.environment=_.isMeshStandardMaterial||_.isMeshLambertMaterial||_.isMeshPhongMaterial?P.environment:null,O.fog=P.fog;let Yt=_.isMeshStandardMaterial||_.isMeshLambertMaterial&&!_.envMap||_.isMeshPhongMaterial&&!_.envMap;O.envMap=xt.get(_.envMap||O.environment,Yt),O.envMapRotation=O.environment!==null&&_.envMap===null?P.environmentRotation:_.envMapRotation,Nt===void 0&&(_.addEventListener("dispose",Ft),Nt=new Map,O.programs=Nt);let ie=Nt.get(yt);if(ie!==void 0){if(O.currentProgram===ie&&O.lightsStateVersion===ct)return zs(_,_t),ie}else _t.uniforms=St.getUniforms(_),D!==null&&_.isNodeMaterial&&D.build(_,H,_t),_.onBeforeCompile(_t,T),ie=St.acquireProgram(_t,yt),Nt.set(yt,ie),O.uniforms=_t.uniforms;let Ut=O.uniforms;return(!_.isShaderMaterial&&!_.isRawShaderMaterial||_.clipping===!0)&&(Ut.clippingPlanes=Ht.uniform),zs(_,_t),O.needsLights=dt(_),O.lightsStateVersion=ct,O.needsLights&&(Ut.ambientLightColor.value=k.state.ambient,Ut.lightProbe.value=k.state.probe,Ut.sunLights.value=k.state.sun,Ut.sunLightShadows.value=k.state.sunShadow,Ut.directionalLights.value=k.state.directional,Ut.directionalLightShadows.value=k.state.directionalShadow,Ut.spotLights.value=k.state.spot,Ut.spotLightShadows.value=k.state.spotShadow,Ut.rectAreaLights.value=k.state.rectArea,Ut.ltc_1.value=k.state.rectAreaLTC1,Ut.ltc_2.value=k.state.rectAreaLTC2,Ut.pointLights.value=k.state.point,Ut.pointLightShadows.value=k.state.pointShadow,Ut.hemisphereLights.value=k.state.hemi,Ut.sunShadowMatrix.value=k.state.sunShadowMatrix,Ut.sunShadowCascade.value=k.state.sunShadowCascade,Ut.directionalShadowMatrix.value=k.state.directionalShadowMatrix,Ut.spotLightMatrix.value=k.state.spotLightMatrix,Ut.spotLightMap.value=k.state.spotLightMap,Ut.pointShadowMatrix.value=k.state.pointShadowMatrix),O.lightProbeGrid=E.state.lightProbeGridArray.length>0,O.currentProgram=ie,O.uniformsList=null,ie}function ta(_){if(_.uniformsList===null){let P=_.currentProgram.getUniforms();_.uniformsList=Hr.seqWithValue(P.seq,_.uniforms)}return _.uniformsList}function zs(_,P){let H=Q.get(_);H.outputColorSpace=P.outputColorSpace,H.batching=P.batching,H.batchingColor=P.batchingColor,H.instancing=P.instancing,H.instancingColor=P.instancingColor,H.instancingMorph=P.instancingMorph,H.skinning=P.skinning,H.morphTargets=P.morphTargets,H.morphNormals=P.morphNormals,H.morphColors=P.morphColors,H.morphTargetsCount=P.morphTargetsCount,H.numClippingPlanes=P.numClippingPlanes,H.numIntersection=P.numClipIntersection,H.vertexAlphas=P.vertexAlphas,H.vertexTangents=P.vertexTangents,H.toneMapping=P.toneMapping}function Za(_,P){if(_.length===0)return null;if(_.length===1)return _[0].texture!==null?_[0]:null;v.setFromMatrixPosition(P.matrixWorld);for(let H=0,O=_.length;H<O;H++){let k=_[H];if(k.texture!==null&&k.boundingBox.containsPoint(v))return k}return null}function Z(_,P,H,O,k){P.isScene!==!0&&(P=Ie),it.resetTextureUnits();let st=P.fog,ct=O.isMeshStandardMaterial||O.isMeshLambertMaterial||O.isMeshPhongMaterial?P.environment:null,_t=G===null?T.outputColorSpace:G.isXRRenderTarget===!0?G.texture.colorSpace:me.workingColorSpace,yt=O.isMeshStandardMaterial||O.isMeshLambertMaterial&&!O.envMap||O.isMeshPhongMaterial&&!O.envMap,Nt=xt.get(O.envMap||ct,yt),Yt=O.vertexColors===!0&&!!H.attributes.color&&H.attributes.color.itemSize===4,ie=!!H.attributes.tangent&&(!!O.normalMap||O.anisotropy>0),Ut=!!H.morphAttributes.position,ue=!!H.morphAttributes.normal,Oe=!!H.morphAttributes.color,Te=ui;O.toneMapped&&(G===null||G.isXRRenderTarget===!0)&&(Te=T.toneMapping);let Se=H.morphAttributes.position||H.morphAttributes.normal||H.morphAttributes.color,Ve=Se!==void 0?Se.length:0,ft=Q.get(O),Be=E.state.lights;if(te===!0&&(ne===!0||_!==K)){let Ne=_===K&&O.id===X;Ht.setState(O,_,Ne)}let oe=!1;O.version===ft.__version?(ft.needsLights&&ft.lightsStateVersion!==Be.state.version||ft.outputColorSpace!==_t||k.isBatchedMesh&&ft.batching===!1||!k.isBatchedMesh&&ft.batching===!0||k.isBatchedMesh&&ft.batchingColor===!0&&k._colorsTexture===null||k.isBatchedMesh&&ft.batchingColor===!1&&k._colorsTexture!==null||k.isInstancedMesh&&ft.instancing===!1||!k.isInstancedMesh&&ft.instancing===!0||k.isSkinnedMesh&&ft.skinning===!1||!k.isSkinnedMesh&&ft.skinning===!0||k.isInstancedMesh&&ft.instancingColor===!0&&k.instanceColor===null||k.isInstancedMesh&&ft.instancingColor===!1&&k.instanceColor!==null||k.isInstancedMesh&&ft.instancingMorph===!0&&k.morphTexture===null||k.isInstancedMesh&&ft.instancingMorph===!1&&k.morphTexture!==null||ft.envMap!==Nt||O.fog===!0&&ft.fog!==st||ft.numClippingPlanes!==void 0&&(ft.numClippingPlanes!==Ht.numPlanes||ft.numIntersection!==Ht.numIntersection)||ft.vertexAlphas!==Yt||ft.vertexTangents!==ie||ft.morphTargets!==Ut||ft.morphNormals!==ue||ft.morphColors!==Oe||ft.toneMapping!==Te||ft.morphTargetsCount!==Ve||!!ft.lightProbeGrid!=E.state.lightProbeGridArray.length>0)&&(oe=!0):(oe=!0,ft.__version=O.version);let fn=ft.currentProgram;oe===!0&&(fn=Ls(O,P,k),D&&O.isNodeMaterial&&D.onUpdateProgram(O,fn,ft));let Fn=!1,On=!1,sr=!1,Pe=fn.getUniforms(),qe=ft.uniforms;if(y.useProgram(fn.program)&&(Fn=!0,On=!0,sr=!0),O.id!==X&&(X=O.id,On=!0),ft.needsLights){let Ne=Za(E.state.lightProbeGridArray,k);ft.lightProbeGrid!==Ne&&(ft.lightProbeGrid=Ne,On=!0)}if(Fn||K!==_){y.buffers.depth.getReversed()&&_.reversedDepth!==!0&&(_._reversedDepth=!0,_.updateProjectionMatrix()),Pe.setValue(Y,"projectionMatrix",_.projectionMatrix),Pe.setValue(Y,"viewMatrix",_.matrixWorldInverse);let rs=Pe.map.cameraPosition;rs!==void 0&&rs.setValue(Y,xe.setFromMatrixPosition(_.matrixWorld)),L.logarithmicDepthBuffer&&Pe.setValue(Y,"logDepthBufFC",2/(Math.log(_.far+1)/Math.LN2)),(O.isMeshPhongMaterial||O.isMeshToonMaterial||O.isMeshLambertMaterial||O.isMeshBasicMaterial||O.isMeshStandardMaterial||O.isShaderMaterial)&&Pe.setValue(Y,"isOrthographic",_.isOrthographicCamera===!0),K!==_&&(K=_,On=!0,sr=!0)}if(ft.needsLights&&(Be.state.sunShadowMap.length>0&&Pe.setValue(Y,"sunShadowMap",Be.state.sunShadowMap,it),Be.state.directionalShadowMap.length>0&&Pe.setValue(Y,"directionalShadowMap",Be.state.directionalShadowMap,it),Be.state.spotShadowMap.length>0&&Pe.setValue(Y,"spotShadowMap",Be.state.spotShadowMap,it),Be.state.pointShadowMap.length>0&&Pe.setValue(Y,"pointShadowMap",Be.state.pointShadowMap,it)),k.isSkinnedMesh){Pe.setOptional(Y,k,"bindMatrix"),Pe.setOptional(Y,k,"bindMatrixInverse");let Ne=k.skeleton;Ne&&(Ne.boneTexture===null&&Ne.computeBoneTexture(),Pe.setValue(Y,"boneTexture",Ne.boneTexture,it))}k.isBatchedMesh&&(Pe.setOptional(Y,k,"batchingTexture"),Pe.setValue(Y,"batchingTexture",k._matricesTexture,it),Pe.setOptional(Y,k,"batchingIdTexture"),Pe.setValue(Y,"batchingIdTexture",k._indirectTexture,it),Pe.setOptional(Y,k,"batchingColorTexture"),k._colorsTexture!==null&&Pe.setValue(Y,"batchingColorTexture",k._colorsTexture,it));let ss=H.morphAttributes;if((ss.position!==void 0||ss.normal!==void 0||ss.color!==void 0)&&W.update(k,H,fn),(On||ft.receiveShadow!==k.receiveShadow)&&(ft.receiveShadow=k.receiveShadow,Pe.setValue(Y,"receiveShadow",k.receiveShadow)),(O.isMeshStandardMaterial||O.isMeshLambertMaterial||O.isMeshPhongMaterial)&&O.envMap===null&&P.environment!==null&&(qe.envMapIntensity.value=P.environmentIntensity),qe.dfgLUT!==void 0&&(qe.dfgLUT.value=L_()),On){if(Pe.setValue(Y,"toneMappingExposure",T.toneMappingExposure),ft.needsLights&&j(qe,sr),st&&O.fog===!0&&Bt.refreshFogUniforms(qe,st),Bt.refreshMaterialUniforms(qe,O,et,J,E.state.transmissionRenderTarget[_.id]),ft.needsLights&&ft.lightProbeGrid){let Ne=ft.lightProbeGrid;qe.probesSH.value=Ne.texture,qe.probesMin.value.copy(Ne.boundingBox.min),qe.probesMax.value.copy(Ne.boundingBox.max),qe.probesResolution.value.copy(Ne.resolution)}Hr.upload(Y,ta(ft),qe,it)}if(O.isShaderMaterial&&O.uniformsNeedUpdate===!0&&(Hr.upload(Y,ta(ft),qe,it),O.uniformsNeedUpdate=!1),O.isSpriteMaterial&&Pe.setValue(Y,"center",k.center),Pe.setValue(Y,"modelViewMatrix",k.modelViewMatrix),Pe.setValue(Y,"normalMatrix",k.normalMatrix),Pe.setValue(Y,"modelMatrix",k.matrixWorld),O.uniformsGroups!==void 0){let Ne=O.uniformsGroups;for(let rs=0,rr=Ne.length;rs<rr;rs++){let nu=Ne[rs];B.update(nu,fn),B.bind(nu,fn)}}return fn}function j(_,P){_.ambientLightColor.needsUpdate=P,_.lightProbe.needsUpdate=P,_.sunLights.needsUpdate=P,_.sunLightShadows.needsUpdate=P,_.directionalLights.needsUpdate=P,_.directionalLightShadows.needsUpdate=P,_.pointLights.needsUpdate=P,_.pointLightShadows.needsUpdate=P,_.spotLights.needsUpdate=P,_.spotLightShadows.needsUpdate=P,_.rectAreaLights.needsUpdate=P,_.hemisphereLights.needsUpdate=P}function dt(_){return _.isMeshLambertMaterial||_.isMeshToonMaterial||_.isMeshPhongMaterial||_.isMeshStandardMaterial||_.isShadowMaterial||_.isShaderMaterial&&_.lights===!0}this.getActiveCubeFace=function(){return q},this.getActiveMipmapLevel=function(){return N},this.getRenderTarget=function(){return G},this.setRenderTargetTextures=function(_,P,H){let O=Q.get(_);O.__autoAllocateDepthBuffer=_.resolveDepthBuffer===!1,O.__autoAllocateDepthBuffer===!1&&(O.__useRenderToTexture=!1),Q.get(_.texture).__webglTexture=P,Q.get(_.depthTexture).__webglTexture=O.__autoAllocateDepthBuffer?void 0:H,O.__hasExternalTextures=!0},this.setRenderTargetFramebuffer=function(_,P){let H=Q.get(_);H.__webglFramebuffer=P,H.__useDefaultFramebuffer=P===void 0},this.setRenderTarget=function(_,P=0,H=0){G=_,q=P,N=H;let O=null,k=!1,st=!1;if(_){let _t=Q.get(_);if(_t.__useDefaultFramebuffer!==void 0){y.bindFramebuffer(Y.FRAMEBUFFER,_t.__webglFramebuffer),nt.copy(_.viewport),tt.copy(_.scissor),lt=_.scissorTest,y.viewport(nt),y.scissor(tt),y.setScissorTest(lt),X=-1;return}else if(_t.__webglFramebuffer===void 0)it.setupRenderTarget(_);else if(_t.__hasExternalTextures)it.rebindTextures(_,Q.get(_.texture).__webglTexture,Q.get(_.depthTexture).__webglTexture);else if(_.depthBuffer){let Yt=_.depthTexture;if(_t.__boundDepthTexture!==Yt){if(Yt!==null&&Q.has(Yt)&&(_.width!==Yt.image.width||_.height!==Yt.image.height))throw new Error("THREE.WebGLRenderer: Attached DepthTexture is initialized to the incorrect size.");it.setupDepthRenderbuffer(_)}}let yt=_.texture;(yt.isData3DTexture||yt.isDataArrayTexture||yt.isCompressedArrayTexture)&&(st=!0);let Nt=Q.get(_).__webglFramebuffer;_.isWebGLCubeRenderTarget?(Array.isArray(Nt[P])?O=Nt[P][H]:O=Nt[P],k=!0):_.samples>0&&it.useMultisampledRTT(_)===!1?O=Q.get(_).__webglMultisampledFramebuffer:Array.isArray(Nt)?O=Nt[H]:O=Nt,nt.copy(_.viewport),tt.copy(_.scissor),lt=_.scissorTest}else nt.copy(Mt).multiplyScalar(et).floor(),tt.copy(qt).multiplyScalar(et).floor(),lt=ve;if(H!==0&&(O=V),y.bindFramebuffer(Y.FRAMEBUFFER,O)&&y.drawBuffers(_,O),y.viewport(nt),y.scissor(tt),y.setScissorTest(lt),k){let _t=Q.get(_.texture);Y.framebufferTexture2D(Y.FRAMEBUFFER,Y.COLOR_ATTACHMENT0,Y.TEXTURE_CUBE_MAP_POSITIVE_X+P,_t.__webglTexture,H)}else if(st){let _t=P;for(let yt=0;yt<_.textures.length;yt++){let Nt=Q.get(_.textures[yt]);Y.framebufferTextureLayer(Y.FRAMEBUFFER,Y.COLOR_ATTACHMENT0+yt,Nt.__webglTexture,H,_t)}}else if(_!==null&&H!==0){let _t=Q.get(_.texture);Y.framebufferTexture2D(Y.FRAMEBUFFER,Y.COLOR_ATTACHMENT0,Y.TEXTURE_2D,_t.__webglTexture,H)}X=-1};function bt(_){let P=Q.get(_);return(P.__readFormat!==_.format||P.__readType!==_.type)&&(P.__readFormat=_.format,P.__readType=_.type,P.__formatReadable=L.textureFormatReadable(_.format),P.__typeReadable=L.textureTypeReadable(_.type)),P}this.readRenderTargetPixels=function(_,P,H,O,k,st,ct,_t=0){if(!(_&&_.isWebGLRenderTarget)){Kt("WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");return}let yt=Q.get(_).__webglFramebuffer;if(_.isWebGLCubeRenderTarget&&ct!==void 0&&(yt=yt[ct]),yt){y.bindFramebuffer(Y.FRAMEBUFFER,yt);try{let Nt=_.textures[_t],Yt=Nt.format,ie=Nt.type;_.textures.length>1&&Y.readBuffer(Y.COLOR_ATTACHMENT0+_t);let Ut=bt(Nt);if(Ut.__formatReadable===!1){Kt("WebGLRenderer.readRenderTargetPixels: renderTarget is not in RGBA or implementation defined format.");return}if(Ut.__typeReadable===!1){Kt("WebGLRenderer.readRenderTargetPixels: renderTarget is not in UnsignedByteType or implementation defined type.");return}P>=0&&P<=_.width-O&&H>=0&&H<=_.height-k&&Y.readPixels(P,H,O,k,Tt.convert(Yt),Tt.convert(ie),st)}finally{let Nt=G!==null?Q.get(G).__webglFramebuffer:null;y.bindFramebuffer(Y.FRAMEBUFFER,Nt)}}},this.readRenderTargetPixelsAsync=async function(_,P,H,O,k,st,ct,_t=0){if(!(_&&_.isWebGLRenderTarget))throw new Error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");let yt=Q.get(_).__webglFramebuffer;if(_.isWebGLCubeRenderTarget&&ct!==void 0&&(yt=yt[ct]),yt)if(P>=0&&P<=_.width-O&&H>=0&&H<=_.height-k){y.bindFramebuffer(Y.FRAMEBUFFER,yt);let Nt=_.textures[_t],Yt=Nt.format,ie=Nt.type;_.textures.length>1&&Y.readBuffer(Y.COLOR_ATTACHMENT0+_t);let Ut=bt(Nt);if(Ut.__formatReadable===!1)throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in RGBA or implementation defined format.");if(Ut.__typeReadable===!1)throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in UnsignedByteType or implementation defined type.");let ue=Y.createBuffer();Y.bindBuffer(Y.PIXEL_PACK_BUFFER,ue),Y.bufferData(Y.PIXEL_PACK_BUFFER,st.byteLength,Y.STREAM_READ),Y.readPixels(P,H,O,k,Tt.convert(Yt),Tt.convert(ie),0),Y.bindBuffer(Y.PIXEL_PACK_BUFFER,null);let Oe=G!==null?Q.get(G).__webglFramebuffer:null;y.bindFramebuffer(Y.FRAMEBUFFER,Oe);let Te=Y.fenceSync(Y.SYNC_GPU_COMMANDS_COMPLETE,0);return Y.flush(),await ud(Y,Te,4),Y.bindBuffer(Y.PIXEL_PACK_BUFFER,ue),Y.getBufferSubData(Y.PIXEL_PACK_BUFFER,0,st),Y.bindBuffer(Y.PIXEL_PACK_BUFFER,null),Y.deleteBuffer(ue),Y.deleteSync(Te),st}else throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: requested read bounds are out of range.")},this.copyFramebufferToTexture=function(_,P=null,H=0){let O=Math.pow(2,-H),k=Math.floor(_.image.width*O),st=Math.floor(_.image.height*O),ct=P!==null?P.x:0,_t=P!==null?P.y:0;it.setTexture2D(_,0),Y.copyTexSubImage2D(Y.TEXTURE_2D,H,0,0,ct,_t,k,st),y.unbindTexture()},this.copyTextureToTexture=function(_,P,H=null,O=null,k=0,st=0){let ct,_t,yt,Nt,Yt,ie,Ut,ue,Oe,Te=_.isCompressedTexture?_.mipmaps[st]:_.image;if(H!==null)ct=H.max.x-H.min.x,_t=H.max.y-H.min.y,yt=H.isBox3?H.max.z-H.min.z:1,Nt=H.min.x,Yt=H.min.y,ie=H.isBox3?H.min.z:0;else{let qe=Math.pow(2,-k);ct=Math.floor(Te.width*qe),_t=Math.floor(Te.height*qe),_.isDataArrayTexture?yt=Te.depth:_.isData3DTexture?yt=Math.floor(Te.depth*qe):yt=1,Nt=0,Yt=0,ie=0}O!==null?(Ut=O.x,ue=O.y,Oe=O.z):(Ut=0,ue=0,Oe=0);let Se=Tt.convert(P.format),Ve=Tt.convert(P.type),ft;P.isData3DTexture?(it.setTexture3D(P,0),ft=Y.TEXTURE_3D):P.isDataArrayTexture||P.isCompressedArrayTexture?(it.setTexture2DArray(P,0),ft=Y.TEXTURE_2D_ARRAY):(it.setTexture2D(P,0),ft=Y.TEXTURE_2D),y.activeTexture(Y.TEXTURE0),y.pixelStorei(Y.UNPACK_FLIP_Y_WEBGL,P.flipY),y.pixelStorei(Y.UNPACK_PREMULTIPLY_ALPHA_WEBGL,P.premultiplyAlpha),y.pixelStorei(Y.UNPACK_ALIGNMENT,P.unpackAlignment);let Be=y.getParameter(Y.UNPACK_ROW_LENGTH),oe=y.getParameter(Y.UNPACK_IMAGE_HEIGHT),fn=y.getParameter(Y.UNPACK_SKIP_PIXELS),Fn=y.getParameter(Y.UNPACK_SKIP_ROWS),On=y.getParameter(Y.UNPACK_SKIP_IMAGES);y.pixelStorei(Y.UNPACK_ROW_LENGTH,Te.width),y.pixelStorei(Y.UNPACK_IMAGE_HEIGHT,Te.height),y.pixelStorei(Y.UNPACK_SKIP_PIXELS,Nt),y.pixelStorei(Y.UNPACK_SKIP_ROWS,Yt),y.pixelStorei(Y.UNPACK_SKIP_IMAGES,ie);let sr=_.isDataArrayTexture||_.isData3DTexture,Pe=P.isDataArrayTexture||P.isData3DTexture;if(_.isDepthTexture){let qe=Q.get(_),ss=Q.get(P),Ne=Q.get(qe.__renderTarget),rs=Q.get(ss.__renderTarget);y.bindFramebuffer(Y.READ_FRAMEBUFFER,Ne.__webglFramebuffer),y.bindFramebuffer(Y.DRAW_FRAMEBUFFER,rs.__webglFramebuffer);for(let rr=0;rr<yt;rr++)sr&&(Y.framebufferTextureLayer(Y.READ_FRAMEBUFFER,Y.COLOR_ATTACHMENT0,Q.get(_).__webglTexture,k,ie+rr),Y.framebufferTextureLayer(Y.DRAW_FRAMEBUFFER,Y.COLOR_ATTACHMENT0,Q.get(P).__webglTexture,st,Oe+rr)),Y.blitFramebuffer(Nt,Yt,ct,_t,Ut,ue,ct,_t,Y.DEPTH_BUFFER_BIT,Y.NEAREST);y.bindFramebuffer(Y.READ_FRAMEBUFFER,null),y.bindFramebuffer(Y.DRAW_FRAMEBUFFER,null)}else if(k!==0||_.isRenderTargetTexture||Q.has(_)){let qe=Q.get(_),ss=Q.get(P);y.bindFramebuffer(Y.READ_FRAMEBUFFER,U),y.bindFramebuffer(Y.DRAW_FRAMEBUFFER,z);for(let Ne=0;Ne<yt;Ne++)sr?Y.framebufferTextureLayer(Y.READ_FRAMEBUFFER,Y.COLOR_ATTACHMENT0,qe.__webglTexture,k,ie+Ne):Y.framebufferTexture2D(Y.READ_FRAMEBUFFER,Y.COLOR_ATTACHMENT0,Y.TEXTURE_2D,qe.__webglTexture,k),Pe?Y.framebufferTextureLayer(Y.DRAW_FRAMEBUFFER,Y.COLOR_ATTACHMENT0,ss.__webglTexture,st,Oe+Ne):Y.framebufferTexture2D(Y.DRAW_FRAMEBUFFER,Y.COLOR_ATTACHMENT0,Y.TEXTURE_2D,ss.__webglTexture,st),k!==0?Y.blitFramebuffer(Nt,Yt,ct,_t,Ut,ue,ct,_t,Y.COLOR_BUFFER_BIT,Y.NEAREST):Pe?Y.copyTexSubImage3D(ft,st,Ut,ue,Oe+Ne,Nt,Yt,ct,_t):Y.copyTexSubImage2D(ft,st,Ut,ue,Nt,Yt,ct,_t);y.bindFramebuffer(Y.READ_FRAMEBUFFER,null),y.bindFramebuffer(Y.DRAW_FRAMEBUFFER,null)}else Pe?_.isDataTexture||_.isData3DTexture?Y.texSubImage3D(ft,st,Ut,ue,Oe,ct,_t,yt,Se,Ve,Te.data):P.isCompressedArrayTexture?Y.compressedTexSubImage3D(ft,st,Ut,ue,Oe,ct,_t,yt,Se,Te.data):Y.texSubImage3D(ft,st,Ut,ue,Oe,ct,_t,yt,Se,Ve,Te):_.isDataTexture?Y.texSubImage2D(Y.TEXTURE_2D,st,Ut,ue,ct,_t,Se,Ve,Te.data):_.isCompressedTexture?Y.compressedTexSubImage2D(Y.TEXTURE_2D,st,Ut,ue,Te.width,Te.height,Se,Te.data):Y.texSubImage2D(Y.TEXTURE_2D,st,Ut,ue,ct,_t,Se,Ve,Te);y.pixelStorei(Y.UNPACK_ROW_LENGTH,Be),y.pixelStorei(Y.UNPACK_IMAGE_HEIGHT,oe),y.pixelStorei(Y.UNPACK_SKIP_PIXELS,fn),y.pixelStorei(Y.UNPACK_SKIP_ROWS,Fn),y.pixelStorei(Y.UNPACK_SKIP_IMAGES,On),st===0&&P.generateMipmaps&&Y.generateMipmap(ft),y.unbindTexture()},this.initRenderTarget=function(_){Q.get(_).__webglFramebuffer===void 0&&it.setupRenderTarget(_)},this.initTexture=function(_){_.isCubeTexture?it.setTextureCube(_,0):_.isData3DTexture?it.setTexture3D(_,0):_.isDataArrayTexture||_.isCompressedArrayTexture?it.setTexture2DArray(_,0):it.setTexture2D(_,0),y.unbindTexture()},this.resetState=function(){q=0,N=0,G=null,y.reset(),It.reset()},typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}get coordinateSystem(){return li}get outputColorSpace(){return this._outputColorSpace}set outputColorSpace(t){this._outputColorSpace=t;let e=this.getContext();e.drawingBufferColorSpace=me._getDrawingBufferColorSpace(t),e.unpackColorSpace=me._getUnpackColorSpace()}};var Oa=new F;function Jn(i,t,e,n,s,r){let a=2*Math.PI*s/4,l=Math.max(r-2*s,0),o=Math.PI/4;Oa.copy(t),Oa[n]=0,Oa.normalize();let c=.5*a/(a+l),h=1-Oa.angleTo(i)/o;return Math.sign(Oa[e])===1?h*c:l/(a+l)+c+c*(1-h)}var Gl=class i extends ce{constructor(t=1,e=1,n=1,s=2,r=.1){let a=s*2+1;if(r=Math.min(t/2,e/2,n/2,r),super(1,1,1,a,a,a),this.type="RoundedBoxGeometry",this.parameters={width:t,height:e,depth:n,segments:s,radius:r},a===1)return;let l=this.toNonIndexed();this.index=null,this.attributes.position=l.attributes.position,this.attributes.normal=l.attributes.normal,this.attributes.uv=l.attributes.uv;let o=new F,c=new F,h=new F(t,e,n).divideScalar(2).subScalar(r),f=this.attributes.position.array,d=this.attributes.normal.array,p=this.attributes.uv.array,x=f.length/6,M=new F,m=.5/a;for(let u=0,b=0;u<f.length;u+=3,b+=2)switch(o.fromArray(f,u),c.copy(o),c.x-=Math.sign(c.x)*m,c.y-=Math.sign(c.y)*m,c.z-=Math.sign(c.z)*m,c.normalize(),f[u+0]=h.x*Math.sign(o.x)+c.x*r,f[u+1]=h.y*Math.sign(o.y)+c.y*r,f[u+2]=h.z*Math.sign(o.z)+c.z*r,d[u+0]=c.x,d[u+1]=c.y,d[u+2]=c.z,Math.floor(u/x)){case 0:M.set(1,0,0),p[b+0]=Jn(M,c,"z","y",r,n),p[b+1]=1-Jn(M,c,"y","z",r,e);break;case 1:M.set(-1,0,0),p[b+0]=1-Jn(M,c,"z","y",r,n),p[b+1]=1-Jn(M,c,"y","z",r,e);break;case 2:M.set(0,1,0),p[b+0]=1-Jn(M,c,"x","z",r,t),p[b+1]=Jn(M,c,"z","x",r,n);break;case 3:M.set(0,-1,0),p[b+0]=1-Jn(M,c,"x","z",r,t),p[b+1]=1-Jn(M,c,"z","x",r,n);break;case 4:M.set(0,0,1),p[b+0]=1-Jn(M,c,"x","y",r,t),p[b+1]=1-Jn(M,c,"y","x",r,e);break;case 5:M.set(0,0,-1),p[b+0]=Jn(M,c,"x","y",r,t),p[b+1]=1-Jn(M,c,"y","x",r,e);break}}static fromJSON(t){return new i(t.width,t.height,t.depth,t.segments,t.radius)}};function Wl(i,t=!1){let e=i[0].index!==null,n=new Set(Object.keys(i[0].attributes)),s=new Set(Object.keys(i[0].morphAttributes)),r={},a={},l=i[0].morphTargetsRelative,o=new je,c=0;for(let h=0;h<i.length;++h){let f=i[h],d=0;if(e!==(f.index!==null))return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+". All geometries must have compatible attributes; make sure index attribute exists among all geometries, or in none of them."),null;for(let p in f.attributes){if(!n.has(p))return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+'. All geometries must have compatible attributes; make sure "'+p+'" attribute exists among all geometries, or in none of them.'),null;r[p]===void 0&&(r[p]=[]),r[p].push(f.attributes[p]),d++}if(d!==n.size)return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+". Make sure all geometries have the same number of attributes."),null;if(l!==f.morphTargetsRelative)return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+". .morphTargetsRelative must be consistent throughout all geometries."),null;for(let p in f.morphAttributes){if(!s.has(p))return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+".  .morphAttributes must be consistent throughout all geometries."),null;a[p]===void 0&&(a[p]=[]),a[p].push(f.morphAttributes[p])}if(t){let p;if(e)p=f.index.count;else if(f.attributes.position!==void 0)p=f.attributes.position.count;else return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+". The geometry must have either an index or a position attribute"),null;o.addGroup(c,p,h),c+=p}}if(e){let h=0,f=[];for(let d=0;d<i.length;++d){let p=i[d].index;for(let x=0;x<p.count;++x)f.push(p.getX(x)+h);h+=i[d].attributes.position.count}o.setIndex(f)}for(let h in r){let f=Xd(r[h]);if(!f)return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed while trying to merge the "+h+" attribute."),null;o.setAttribute(h,f)}for(let h in a){let f=a[h][0].length;if(f!==0){o.morphAttributes=o.morphAttributes||{},o.morphAttributes[h]=[];for(let d=0;d<f;++d){let p=[];for(let M=0;M<a[h].length;++M)p.push(a[h][M][d]);let x=Xd(p);if(!x)return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed while trying to merge the "+h+" morphAttribute."),null;o.morphAttributes[h].push(x)}}}return o}function Xd(i){let t,e,n,s=-1,r=0;for(let c=0;c<i.length;++c){let h=i[c];if(t===void 0&&(t=h.array.constructor),t!==h.array.constructor)return console.error("THREE.BufferGeometryUtils: .mergeAttributes() failed. BufferAttribute.array must be of consistent array types across matching attributes."),null;if(e===void 0&&(e=h.itemSize),e!==h.itemSize)return console.error("THREE.BufferGeometryUtils: .mergeAttributes() failed. BufferAttribute.itemSize must be consistent across matching attributes."),null;if(n===void 0&&(n=h.normalized),n!==h.normalized)return console.error("THREE.BufferGeometryUtils: .mergeAttributes() failed. BufferAttribute.normalized must be consistent across matching attributes."),null;if(s===-1&&(s=h.gpuType),s!==h.gpuType)return console.error("THREE.BufferGeometryUtils: .mergeAttributes() failed. BufferAttribute.gpuType must be consistent across matching attributes."),null;r+=h.count*e}let a=new t(r),l=new pn(a,e,n),o=0;for(let c=0;c<i.length;++c){let h=i[c];if(h.isInterleavedBufferAttribute){let f=o/e;for(let d=0,p=h.count;d<p;d++)for(let x=0;x<e;x++){let M=h.getComponent(d,x);l.setComponent(d+f,x,M)}}else a.set(h.array,o);o+=h.count*e}return s!==void 0&&(l.gpuType=s),l}function ql(){return{matte:new Me({vertexColors:!0,roughness:.84,metalness:0}),satin:new Me({vertexColors:!0,roughness:.42,metalness:.05}),metal:new Me({vertexColors:!0,roughness:.38,metalness:.55}),glass:new Me({vertexColors:!0,roughness:.08,metalness:.1,transparent:!0,opacity:.55,depthWrite:!1}),glow:new be({vertexColors:!0,toneMapped:!1})}}function Yl(i){for(let t of Object.values(i))t.dispose()}var qd=new Map;function Ks(i,t){let e=qd.get(i);return e||(e=t(),qd.set(i,e)),e}var z_=.02;function I(i,t,e,n=0){let s=Math.min(n,i/2,t/2,e/2);return Ks(`box:${i}:${t}:${e}:${s}`,()=>s>=z_?new Gl(i,t,e,1,s):new ce(i,t,e))}function Ot(i,t,e,n=16){return Ks(`cyl:${i}:${t}:${e}:${n}`,()=>new Ir(i,t,e,n))}function Le(i,t=12,e=8){return Ks(`sph:${i}:${t}:${e}`,()=>new Vs(i,t,e))}function Ki(i,t,e=8){return Ks(`cone:${i}:${t}:${e}`,()=>new va(i,t,e))}function gn(i,t,e=Math.PI*2,n=8,s=24){return Ks(`torus:${i}:${t}:${e}:${n}:${s}`,()=>new Ma(i,t,n,s,e))}function Kd(i,t,e=16){return Ks(`capsule:${i}:${t}:${e}`,()=>new ya(i,t,6,e))}function jn(i){return Ks(`dodeca:${i}`,()=>new ba(i,0))}var D_=new ge,Yd=new Ye,N_=new Ln,Zd=new F,$d=new F,Xl=new $t;function U_(i,t,e){let n=i.index?i.toNonIndexed():i.clone();n.deleteAttribute("uv"),Zd.set(t.x??0,t.y??0,t.z??0),Yd.setFromEuler(N_.set(t.rx??0,t.ry??0,t.rz??0)),$d.set(t.sx??1,t.sy??1,t.sz??1),n.applyMatrix4(D_.compose(Zd,Yd,$d)),Xl.set(e);let s=n.getAttribute("position").count,r=new Float32Array(s*3);for(let a=0;a<s;a+=1)r[a*3]=Xl.r,r[a*3+1]=Xl.g,r[a*3+2]=Xl.b;return n.setAttribute("color",new pn(r,3)),n}var ee=class{constructor(){ae(this,"groups",new Map);ae(this,"frame",null)}add(t,e,n={},s="matte",r=!0){let a=`${s}|${r?1:0}`,l=this.groups.get(a);l||(l=[],this.groups.set(a,l));let o=U_(t,n,e);this.frame&&o.applyMatrix4(this.frame),l.push(o)}within(t,e){let n=this.frame,s=new ge().compose(new F(t.x??0,t.y??0,t.z??0),new Ye().setFromEuler(new Ln(t.rx??0,t.ry??0,t.rz??0)),new F(t.sx??1,t.sy??1,t.sz??1));this.frame=n?n.clone().multiply(s):s;try{e()}finally{this.frame=n}}build(){let t=[];for(let[e,n]of this.groups){let[s,r]=e.split("|"),a=Wl(n,!1);for(let l of n)l.dispose();a&&(a.computeBoundingSphere(),t.push({geometry:a,finish:s,shadow:r==="1"}))}return this.groups.clear(),t}};function Ii(i,t,e=!0){return i.map(({geometry:n,finish:s,shadow:r})=>{let a=new kt(n,t[s]);return a.castShadow=r&&s!=="glass"&&s!=="glow",a.receiveShadow=e&&s!=="glow",a.matrixAutoUpdate=!1,a.updateMatrix(),a})}var Gt={x0:-6,x1:6,z0:-4.5,z1:4.5},Ba=2.6,Qn=.18;function Wn(i){return i?{wall:"#4d5466",wallLow:"#434a5b",trim:"#262a33",skirt:"#2b2f38",sky:"#1d2e5c",frame:"#2c303a",wood:"#4e3b2c",woodLight:"#5f4836",deskTop:"#6b5a4a",deskFrame:"#3a3f4b",chair:"#2f3442",seat:"#3d4456",pot:"#8a5a44",soil:"#3a2a20",leaf:"#4f8a5b",leafLight:"#6aa86f",metal:"#5d6470",dim:"#203048"}:{wall:"#f1ece4",wallLow:"#e6ddd0",trim:"#d9cfc1",skirt:"#e9e4dc",sky:"#bfe3ff",frame:"#e8e2d8",wood:"#a5784f",woodLight:"#bf9468",deskTop:"#e8dccb",deskFrame:"#9aa1ab",chair:"#4c5566",seat:"#5c677c",pot:"#c1785a",soil:"#5a4030",leaf:"#4f8a5b",leafLight:"#6aa86f",metal:"#9aa1ab",dim:"#203048"}}function ka(i,t){let e=document.createElement("canvas");e.width=i,e.height=i,t(e.getContext("2d"));let n=new qi(e);return n.wrapS=Si,n.wrapT=Si,n.colorSpace=Ge,n.anisotropy=4,n}function F_(i,t){if(i==="wood")return ka(512,n=>{n.fillStyle=t?"#76604b":"#c9a37c",n.fillRect(0,0,512,512);for(let s=0;s<8;s+=1){let r=s%2*128;for(let a=-1;a<3;a+=1){let l=(s*7+a*3)%5/5;n.fillStyle=t?`rgba(0,0,0,${.08+l*.08})`:`rgba(90,55,25,${.05+l*.07})`,n.fillRect(a*256+r+2,s*64+2,252,60)}}});if(i==="raised")return ka(512,n=>{n.fillStyle=t?"#5a606c":"#c9ced6",n.fillRect(0,0,512,512);for(let s=0;s<4;s+=1)for(let r=0;r<4;r+=1)if(n.fillStyle=t?"#646b78":"#d6dbe2",n.fillRect(r*128+3,s*128+3,122,122),(s+r)%3===0){n.fillStyle=t?"#3e434d":"#9aa1ab";for(let a=0;a<8;a+=1)for(let l=0;l<8;l+=1)n.fillRect(r*128+14+l*13,s*128+14+a*13,5,5)}});if(i==="tile"||i==="stone")return ka(512,n=>{n.fillStyle=i==="stone"?t?"#6d6a66":"#e4ded4":t?"#5d6470":"#dfe2e6",n.fillRect(0,0,512,512);let s=i==="stone"?256:128;for(let r=0;r<512/s;r+=1)for(let a=0;a<512/s;a+=1){let l=(r*5+a*3)%4/4;n.fillStyle=t?`rgba(255,255,255,${.02+l*.03})`:`rgba(0,0,0,${.02+l*.03})`,n.fillRect(a*s+2,r*s+2,s-4,s-4),i==="stone"&&(n.strokeStyle=t?"rgba(255,255,255,0.05)":"rgba(120,110,95,0.12)",n.beginPath(),n.moveTo(a*s+s*.2,r*s+s*(.3+l*.4)),n.bezierCurveTo(a*s+s*.5,r*s+s*.1,a*s+s*.6,r*s+s*.9,a*s+s*.9,r*s+s*.6),n.stroke())}});if(i==="carpet")return ka(256,n=>{n.fillStyle=t?"#3c4456":"#c8cfdb",n.fillRect(0,0,256,256);for(let s=0;s<900;s+=1)n.fillStyle=t?"rgba(255,255,255,0.03)":"rgba(0,0,0,0.04)",n.fillRect(s*97%256,s*61%256,2,2)});let e=i==="lawn";return ka(256,n=>{n.fillStyle=e?t?"#2f4a3a":"#9cc49a":t?"#5a4a3a":"#c8b08a",n.fillRect(0,0,256,256);for(let s=0;s<700;s+=1){let r=s*13%3===0;n.fillStyle=r?t?"rgba(255,255,255,0.05)":"rgba(255,255,255,0.18)":t?"rgba(0,0,0,0.12)":"rgba(80,60,30,0.1)",n.fillRect(s*89%256,s*47%256,2+s%3,2)}})}function Li(i,t,e,n=4){let s=e.x1-e.x0,r=e.z1-e.z0,a=F_(i,t);a.repeat.set(s/n,r/n);let l=new ce(s,.24,r);l.translate((e.x0+e.x1)/2,-.12,(e.z0+e.z1)/2);let o=new Me({map:a,roughness:i==="stone"||i==="tile"?.55:.85}),c=new kt(l,o);return c.receiveShadow=!0,c.matrixAutoUpdate=!1,{mesh:c,dispose(){l.dispose(),o.dispose(),a.dispose()}}}function Wr(i,t,e={},n){let s=Wn(t),r=Gt,a=r.x1-r.x0,l=r.z1-r.z0,o=e.wall??s.wall,c=e.low??s.wallLow,h=.95;i.add(I(a+.1,.12,l+.1),s.skirt,{y:-.3},"matte",!1),i.add(I(a,h,Qn+.02),c,{y:h/2,z:r.z0-Qn/2}),i.add(I(a,Ba-h,Qn),o,{y:h+(Ba-h)/2,z:r.z0-Qn/2}),i.add(I(Qn+.02,h,l+Qn),c,{x:r.x0-Qn/2,y:h/2,z:-Qn/2}),i.add(I(Qn,Ba-h,l+Qn),o,{x:r.x0-Qn/2,y:h+(Ba-h)/2,z:-Qn/2});for(let[f,d]of[[.06,.12],[h,.04],[Ba-.02,.05]])i.add(I(a,d,.04),s.trim,{y:f,z:r.z0+.02},"satin",!1),i.add(I(.04,d,l),s.trim,{x:r.x0+.02,y:f},"satin",!1);if(n){i.add(I(n.width+.2,1.36,.06,.02),s.frame,{x:n.x,y:1.62,z:r.z0+.03},"satin",!1),i.add(I(n.width,1.14,.02),s.sky,{x:n.x,y:1.62,z:r.z0+.065},"glow",!1);let f=Math.max(2,Math.round(n.width/1.1));for(let d=1;d<f;d+=1)i.add(I(.06,1.16,.05),s.frame,{x:n.x-n.width/2+n.width/f*d,y:1.62,z:r.z0+.08},"satin",!1);i.add(I(n.width+.3,.05,.16,.015),s.trim,{x:n.x,y:.92,z:r.z0+.08},"satin",!1)}}function Ji(i,t,e,n,s=!1){let r=Wn(t);i.add(Ot(.21,.15,.38,18),r.pot,{x:e,y:.19,z:n},"satin"),i.add(gn(.205,.02,Math.PI*2,6,18),r.pot,{x:e,y:.38,z:n,rx:Math.PI/2},"satin",!1),i.add(Ot(.19,.19,.02,16),r.soil,{x:e,y:.36,z:n},"matte",!1),s&&i.add(Ot(.02,.025,.7,6),"#5b4636",{x:e,y:.7,z:n},"matte");let a=s?1.05:.58;for(let[l,o,c,h,f]of[[0,0,0,.3,!1],[.14,.12,.05,.2,!0],[-.12,.16,-.06,.18,!0],[.02,.3,.02,.17,!1]])i.add(jn(h*(s?.9:1)),f?r.leafLight:r.leaf,{x:e+l,y:a+o,z:n+c,ry:l*7},"matte")}function Zl(i,t,e,n,s=1.2){let r=Wn(t),a=.7,l=n-.75;i.add(I(s,.045,a,.015),r.deskTop,{x:e,y:.645,z:n},"satin");for(let o of[-1,1])i.add(I(.04,.62,a-.06,.01),r.deskFrame,{x:e+o*(s/2-.05),y:.31,z:n},"metal");return i.add(I(.22,.014,.14,.006),"#2a2d35",{x:e,y:.674,z:n+.2},"metal"),i.add(I(.04,.2,.03),"#5d6470",{x:e,y:.77,z:n+.22},"metal"),i.add(I(.64,.4,.035,.014),"#1d2027",{x:e,y:1,z:n+.2},"satin"),i.add(I(.38,.018,.13,.006),"#2a2d35",{x:e,y:.676,z:n-.12},"satin"),i.add(I(.46,.07,.44,.03),r.seat,{x:e,y:.29,z:l},"matte"),i.add(I(.44,.46,.06,.03),r.chair,{x:e,y:.62,z:l-.23,rx:-.08},"matte"),i.add(Ot(.025,.025,.2,10),"#5d6470",{x:e,y:.16,z:l},"metal"),i.add(Ot(.2,.22,.03,12),"#3a3f4b",{x:e,y:.03,z:l},"metal",!1),new F(e,1,n+.18)}var TS=I(.58,.34,.008);function cn(i,t){let e=new se;for(let n of Ii(i.build(),t))e.add(n);return e}function An(i){i.traverse(t=>{t instanceof kt&&!t.userData.shared&&t.geometry.dispose()})}function zh(i,t=0){let e=2166136261^t;for(let n of i)e=Math.imul(e^n.codePointAt(0),16777619);return(e>>>0)%10007/10007}var O_={x0:-14,x1:14,z0:-10,z1:11},pi={studio:{x:0,z:-5.5,top:0},library:{x:-9,z:-4.5,top:3.3},site:{x:9,z:-4.5,top:2.6},duty:{x:9,z:4.5,top:4.4},desk:{x:0,z:7.5,top:2.9}},ji=1.15,Jd=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Wn(r),l=Li("lawn",r,O_,6);t.add(l.mesh);let o=new ee,c=r?"#5d5a56":"#e4ded4";o.add(Ot(3.2,3.2,.04,40),c,{y:.02},"matte",!1);for(let T of Object.values(pi)){let C=Math.hypot(T.x,T.z);o.add(I(1.1,.035,C),c,{x:T.x/2,y:.018,z:T.z/2,ry:Math.atan2(T.x,T.z)},"matte",!1)}o.add(Ot(.9,1,.3,24),r?"#6f6b66":"#cfc8bc",{y:.15},"satin"),o.add(Ot(.75,.75,.04,24),r?"#2d4f73":"#7fb6d6",{y:.3},"glass",!1);for(let[T,C]of[[-3.5,-2.5],[3.5,-2.5],[-3.5,3],[3.5,3]])o.add(Ot(.05,.07,2.5,8),a.metal,{x:T,y:1.25,z:C},"metal"),o.add(Le(.16,10,8),"#ffe2a8",{x:T,y:2.6,z:C},r?"glow":"satin",!1);for(let[T,C,D]of[[-13,-8.5,1],[-5,-9,.8],[5,-9,.9],[13,-8.5,1],[-13,0,.9],[13,0,1],[-12.5,9.5,1],[-5,10,.8],[5,10,.9],[12.5,9.5,1],[-4.5,2.2,.7],[4.5,2.2,.7],[-10,3.6,1.1],[-7.8,5.4,.85],[-10.6,6.2,.9]])o.add(Ot(.08*D,.11*D,.9*D,8),"#5b4636",{x:T,y:.45*D,z:C},"matte"),o.add(jn(.6*D),a.leaf,{x:T,y:1.15*D,z:C},"matte"),o.add(jn(.42*D),a.leafLight,{x:T+.25*D,y:1.45*D,z:C-.1},"matte");let h=r?"#5a6274":"#efe9df",f=r?"#3a3f4b":"#b8b2a8",d=r?"#1d2e5c":"#9fc9e6";{let{x:T,z:C}=pi.library;o.add(I(5.2,.3,3.6,.03),c,{x:T,y:.15,z:C},"matte"),o.add(I(4.6,2.2,2.8,.03),h,{x:T,y:1.4,z:C-.2},"satin");for(let D=0;D<6;D+=1)o.add(Ot(.13,.15,2.2,12),c,{x:T-2+D*.8,y:1.4,z:C+1.45},"satin");o.add(I(5,.25,3.3,.02),c,{x:T,y:2.62,z:C},"satin"),o.add(Ki(2.9,.75,4),f,{x:T,y:3.1,z:C,ry:Math.PI/4,sz:.62},"satin")}{let{x:T,z:C}=pi.site;o.add(I(5,.03,4.2),r?"#5a4a3a":"#c8b08a",{x:T,y:.02,z:C},"matte",!1);for(let[D,V,U,z]of[[0,-2.1,5,.04],[0,2.1,5,.04],[-2.5,0,.04,4.2],[2.5,0,.04,4.2]])o.add(I(U,.8,z),r?"#3c4c5e":"#7d97b0",{x:T+D,y:.4,z:C+V},"glass",!1);for(let[D,V,U,z]of[[-1.5,-.8,1.2,"#5b7db1"],[-.7,-.9,.8,"#4f8a5b"],[-1.4,.6,.6,"#e3dccb"],[-.5,.5,1.5,"#5b7db1"],[.4,.9,.5,"#9aa1ab"]])o.add(I(.6,U,.6,.02),z,{x:T+D,y:U/2,z:C+V},"satin");o.add(I(.14,3.6,.14),"#e0a13a",{x:T+1.6,y:1.8,z:C-1.2},"metal"),o.add(I(4,.12,.14),"#e0a13a",{x:T+.4,y:3.6,z:C-1.2},"metal"),o.add(Ot(.01,.01,1.4,4),"#2a2d35",{x:T-1.2,y:2.9,z:C-1.2},"metal",!1)}{let{x:T,z:C}=pi.duty;o.add(I(3.8,1.8,3,.04),h,{x:T,y:.9,z:C},"satin"),o.add(Ki(2.8,1,4),f,{x:T,y:2.3,z:C,ry:Math.PI/4,sz:.8},"satin"),o.add(I(1,3.6,1,.03),h,{x:T+1.2,y:1.8,z:C+.6},"satin"),o.add(Ki(.8,.8,4),f,{x:T+1.2,y:4,z:C+.6,ry:Math.PI/4},"satin"),o.add(Ot(.38,.38,.04,24),"#fbfaf7",{x:T+1.2,y:3,z:C+1.11,rx:Math.PI/2},"satin",!1),o.add(gn(.38,.03,Math.PI*2,6,24),"#3b3b40",{x:T+1.2,y:3,z:C+1.13},"metal",!1),o.add(I(.6,1.2,.04),a.wood,{x:T-.5,y:.6,z:C+1.51},"satin",!1)}{let{x:T,z:C}=pi.desk;o.add(I(4,1.7,2.4,.04),h,{x:T,y:.85,z:C},"satin"),o.add(I(4.4,.14,2.8,.03),f,{x:T,y:1.77,z:C+.1},"satin"),o.add(I(1.6,1.3,.04),d,{x:T+.8,y:.75,z:C+1.21},"glass",!1),o.add(Ot(.04,.06,1.8,8),a.metal,{x:T-1.5,y:2.7,z:C},"metal")}o.add(I(4.8,.35,4.8,.04),c,{x:pi.studio.x,y:.17,z:pi.studio.z},"matte"),t.add(cn(o,e));let p=new se;t.add(p);let x=new Map,M=(T,C)=>{let D=new be({color:a.dim,toneMapped:!1});x.set(T,D);let V=new ce(1,1,1);for(let[U,z,q,N,G,X]of C){let K=new kt(V,D);K.position.set(U,z,q),K.scale.set(N,G,X),t.add(K)}},m=pi;M("library",[[m.library.x-1.2,1.5,m.library.z+1.21,.7,1,.03],[m.library.x,1.5,m.library.z+1.21,.7,1,.03],[m.library.x+1.2,1.5,m.library.z+1.21,.7,1,.03]]),M("site",[[m.site.x+.4,3.75,m.site.z-1.2,.18,.18,.18]]),M("duty",[[m.duty.x-.5,1.2,m.duty.z+1.52,.9,.6,.03],[m.duty.x+.9,1,m.duty.z-1.52,.9,.6,.03]]),M("desk",[[m.desk.x-1,1,m.desk.z+1.22,1,.6,.03],[m.desk.x-1.5,3.65,m.desk.z,.12,.12,.12]]);let u=new be({color:a.dim,toneMapped:!1});x.set("studio",u);let b=new Me({color:"#25252a",roughness:.5}),A=new kt(new ce(.04,.22,.01).translate(0,.1,0),b),v=new kt(new ce(.03,.32,.01).translate(0,.15,0),b);A.position.set(m.duty.x+1.2,3,m.duty.z+1.16),v.position.set(m.duty.x+1.2,3,m.duty.z+1.17),t.add(A,v);let S=new be({visible:!1});for(let[T,C]of Object.entries(pi)){let D=new kt(new ce(5.2,T==="studio"?8:C.top+.4,4.2),S);D.position.set(C.x,(T==="studio"?8:C.top+.4)/2,C.z),t.add(D),i.pickable(D,`place:${T}`)}let E=0,R=null,g=T=>{if(T===E)return;E=T;for(let z of[...p.children])z.removeFromParent(),z instanceof kt&&z.material===u?z.geometry.dispose():An(z);let C=new ee,{x:D,z:V}=m.studio;for(let z=0;z<T;z+=1){let q=.35+z*ji;C.add(I(4,ji-.08,4,.03),h,{x:D,y:q+ji/2,z:V},"satin"),C.add(I(4.1,.08,4.1,.02),a.trim,{x:D,y:q+ji-.04,z:V},"satin",!1)}C.add(I(4.3,.2,4.3,.03),f,{x:D,y:.35+T*ji+.1,z:V},"satin"),C.add(Ot(.04,.05,1.2,8),a.metal,{x:D+1.5,y:.35+T*ji+.8,z:V-1.5},"metal"),p.add(cn(C,e));let U=new ce(1,1,1);for(let z=0;z<T;z+=1){let q=.35+z*ji+ji/2;for(let[N,G,X,K]of[[D,V+2.01,3.4,.03],[D+2.01,V,.03,3.4]]){let nt=new kt(U,u);nt.position.set(N,q,G),nt.scale.set(X,.45,K),nt.userData.level=z,p.add(nt)}}};g(1);let w=T=>T==="studio"?.35+E*ji+1:m[T].top+.5;return{frame:{min:{x:-12.5,y:0,z:-8.5},max:{x:12.5,y:4,z:9.5},polar:.95,azimuth:.55},lamps:[{x:-3.5,y:2.6,z:-2.5},{x:3.5,y:2.6,z:-2.5},{x:-3.5,y:2.6,z:3},{x:3.5,y:2.6,z:3}],update({model:T,t:C}){R=T,g(Math.max(1,Math.min(6,T.floors)));let D={};for(let V of Object.keys(pi)){let U=T.spots[V];D[V]={at:{x:m[V].x,y:w(V),z:m[V].z},title:C(`places.${V}.title`),detail:U.detail,...U.alert?{tone:"alert"}:U.busy?{tone:"busy"}:{},pick:`place:${V}`}}return{people:[],labels:D}},tick(T){let C=new Date;v.rotation.z=-((C.getMinutes()+C.getSeconds()/60)/60)*Math.PI*2,A.rotation.z=-((C.getHours()%12+C.getMinutes()/60)/12)*Math.PI*2;for(let[D,V]of x){let U=R?.spots[D],z=s?1:.85+Math.sin(T*(D==="site"||D==="desk"?5:1.5))*.15;U?.alert?V.color.set("#f2b33d").multiplyScalar(z):U?.busy?V.color.set(r?"#ffd27a":"#ffcf6a").multiplyScalar(z):V.color.set(r?"#2a3550":"#7d8ea3")}return!1},target(T){let C=T.startsWith("place:")?T.slice(6):null;return!C||!(C in pi)?null:{x:m[C].x,y:C==="studio"?1.6:1,z:m[C].z}},dispose(){l.dispose();for(let T of[...t.children])An(T);for(let T of x.values())T.dispose();b.dispose(),S.dispose()}}};var B_={lead:{shirt:"#2f5d9e",pants:"#2b3140",skin:"#f1c7a5",hair:"#2b211c",hairStyle:"short",accessory:"badge"},legal:{shirt:"#3e3f55",pants:"#22232c",skin:"#efc6a6",hair:"#1e1a18",hairStyle:"bun",accessory:"tie"},teacher:{shirt:"#8a8d3b",pants:"#3b3a30",skin:"#d39b78",hair:"#4a4a4a",hairStyle:"short",accessory:"glasses"}},jd=["#3f88c5","#d1495b","#66a182","#edae49","#8f6593","#00798c","#e76f51"],Qd=["#2b211c","#6b3e26","#a0522d","#1b1b1b","#c19a6b"],tf=["short","long","bun","spiky"],ef=["none","glasses","scarf","cap"];function k_(i){let t=2166136261;for(let e of i)t=Math.imul(t^e.codePointAt(0),16777619);return t>>>0}function zi(i){let t=B_[i];if(t)return t;let e=k_(i);return{shirt:jd[e%jd.length],pants:"#30343e",skin:["#f1c7a5","#d8a483","#c99272","#e9b896"][(e>>3)%4],hair:Qd[(e>>5)%Qd.length],hairStyle:tf[(e>>7)%tf.length],accessory:ef[(e>>9)%ef.length]}}var Ct={x0:-6,x1:6,z0:-4.5,z1:4.5,height:2.6},$l=[0,-1.8,1.8,-3.6,3.6],Dh=$l.length,nf=-2.2,Qi={width:1.2,depth:.7},Di=-2.95;function Xr(i){return{x:$l[i%$l.length],z:nf}}function Ha(i){let{x:t}=Xr(i);return{x:t,z:Di,face:{x:t,z:nf+2},sit:!0}}var hn={x0:-6,x1:-5.6,z0:-2,z1:-.2},sf=[-1.6,-1.1,-.6].map(i=>({x:-5.15,z:i,face:{x:-7,z:i},sit:!1})),ti={x:-5.92,z0:.4,z1:1.9},rf={x:-5,z:1.15,face:{x:-7,z:1.15},sit:!1},un={x0:5.25,x1:5.9,z0:-4.3,z1:-3.3},dn={x0:5.35,x1:5.9,z0:-3.1,z1:-1.7},af=[{x:4.95,z:-2.05,face:{x:7,z:-2.05},sit:!1}],he={x:4.4,z:-2.4,door:{x0:4.55,x1:5.2}},of=[{x:4.95,z:-2.75,face:{x:7,z:-2.75},sit:!1},{x:4.75,z:-3.65,face:{x:7,z:-3.65},sit:!1}],lf={x:4.85,z:-1.9,face:{x:3.2,z:1.5},sit:!1},we={x:1.6,z:1.5,radius:.85},qr=Array.from({length:6},(i,t)=>{let e=t/6*Math.PI*2+Math.PI/6;return{x:we.x+Math.cos(e)*1.4,z:we.z+Math.sin(e)*1.4,face:{x:we.x,z:we.z},sit:!0}}),$e={x0:-5.75,x1:-5.05,z0:2.3,z1:4.1},H_=[2.8,3.6].map(i=>({x:-4.8,z:i,face:{x:0,z:i},sit:!0})),Nn={x0:-3.3,x1:-1.9,z0:3.95,z1:4.45},V_={x:-2.6,z:3.35,face:{x:-2.6,z:6},sit:!1},Xn={x:5.1,z:3.3},G_={x:4.5,z:3.3,face:{x:7,z:3.3},sit:!1},Nh=[{x:-5.5,z:-4},{x:5.45,z:4.05},{x:-.6,z:4.1},{x:4.05,z:-4.05}],Ni={x0:.7,x1:2.3,z0:3.9,z1:4.42},Kl=[-.9,.9].map(i=>({x:i,z:-3.85,face:{x:i,z:-7},sit:!1})),vn={x0:-5.1,x1:-4.4,z0:-4.4,z1:-3.85},Uh={x:-4.75,z:-3.25,face:{x:-4.75,z:-6},sit:!1},We={x:Ct.x1,z0:.6,z1:1.8},Yr={x:Ct.x1+.9,z:(We.z0+We.z1)/2,face:{x:Ct.x1+4,z:(We.z0+We.z1)/2},sit:!1},Va=[V_,G_,...H_,Kl[1]];function cf(){let i=$l.map((e,n)=>{let{x:s,z:r}=Xr(n);return{x0:s-Qi.width/2,x1:s+Qi.width/2,z0:r-Qi.depth/2,z1:r+Qi.depth/2}}),t=Nh.map(({x:e,z:n})=>({x0:e-.25,x1:e+.25,z0:n-.25,z1:n+.25}));return[...i,hn,un,dn,{x0:he.x-.04,x1:he.x+.04,z0:Ct.z0,z1:he.z},{x0:he.x-.04,x1:he.door.x0,z0:he.z-.04,z1:he.z+.04},{x0:we.x-we.radius,x1:we.x+we.radius,z0:we.z-we.radius,z1:we.z+we.radius},$e,Nn,vn,{x0:Xn.x-.2,x1:Xn.x+.2,z0:Xn.z-.2,z1:Xn.z+.2},Ni,...t]}var Js=.2,Jl=.18,ei=class{constructor(t,e=Ct){ae(this,"columns");ae(this,"rows");ae(this,"blocked");ae(this,"bounds");this.bounds={x0:e.x0,x1:e.x1,z0:e.z0,z1:e.z1},this.columns=Math.round((e.x1-e.x0)/Js),this.rows=Math.round((e.z1-e.z0)/Js),this.blocked=new Uint8Array(this.columns*this.rows);for(let n=0;n<this.rows;n+=1)for(let s=0;s<this.columns;s+=1){let{x:r,z:a}=this.center(s,n),l=r<e.x0+.25||r>e.x1-.15||a<e.z0+.25||a>e.z1-.15,o=t.some(c=>r>c.x0-Jl&&r<c.x1+Jl&&a>c.z0-Jl&&a<c.z1+Jl);this.blocked[n*this.columns+s]=l||o?1:0}}center(t,e){return{x:this.bounds.x0+(t+.5)*Js,z:this.bounds.z0+(e+.5)*Js}}cell(t){let e=Math.min(this.columns-1,Math.max(0,Math.floor((t.x-this.bounds.x0)/Js))),n=Math.min(this.rows-1,Math.max(0,Math.floor((t.z-this.bounds.z0)/Js)));return[e,n]}isBlocked(t,e){return t<0||e<0||t>=this.columns||e>=this.rows?!0:this.blocked[e*this.columns+t]===1}nearestFree(t){let[e,n]=this.cell(t);if(!this.isBlocked(e,n))return[e,n];for(let s=1;s<12;s+=1){let r=null,a=1/0;for(let l=-s;l<=s;l+=1)for(let o=-s;o<=s;o+=1){if(Math.max(Math.abs(o),Math.abs(l))!==s||this.isBlocked(e+o,n+l))continue;let c=this.center(e+o,n+l),h=(c.x-t.x)**2+(c.z-t.z)**2;h<a&&(a=h,r=[e+o,n+l])}if(r)return r}return[e,n]}clear(t,e){let n=Math.ceil(Math.hypot(e.x-t.x,e.z-t.z)/(Js/2));for(let s=1;s<n;s+=1){let r=s/n,[a,l]=this.cell({x:t.x+(e.x-t.x)*r,z:t.z+(e.z-t.z)*r});if(this.isBlocked(a,l))return!1}return!0}path(t,e){if(this.clear(t,e))return[e];let[n,s]=this.nearestFree(t),[r,a]=this.nearestFree(e),l=this.columns*this.rows,o=s*this.columns+n,c=a*this.columns+r,h=new Float32Array(l).fill(1/0),f=new Int32Array(l).fill(-1),d=new Uint8Array(l),p=[o],x=new Float32Array(l).fill(1/0),M=S=>{let E=Math.abs(S%this.columns-r),R=Math.abs(Math.floor(S/this.columns)-a);return Math.max(E,R)+(Math.SQRT2-1)*Math.min(E,R)};for(h[o]=0,x[o]=M(o);p.length>0;){let S=0;for(let w=1;w<p.length;w+=1)x[p[w]]<x[p[S]]&&(S=w);let E=p[S];if(p[S]=p[p.length-1],p.pop(),E===c)break;if(d[E])continue;d[E]=1;let R=E%this.columns,g=Math.floor(E/this.columns);for(let w=-1;w<=1;w+=1)for(let T=-1;T<=1;T+=1){if(!T&&!w)continue;let C=R+T,D=g+w;if(this.isBlocked(C,D)||T&&w&&(this.isBlocked(R+T,g)||this.isBlocked(R,g+w)))continue;let V=D*this.columns+C,U=h[E]+(T&&w?Math.SQRT2:1);U<h[V]&&(h[V]=U,f[V]=E,x[V]=U+M(V),p.push(V))}}if(f[c]===-1&&c!==o)return[e];let m=[];for(let S=c;S!==-1&&S!==o;S=f[S])m.push(this.center(S%this.columns,Math.floor(S/this.columns)));m.reverse();let u=[...m,e],b=[],A=t,v=0;for(;v<u.length;){let S=v;for(let E=u.length-1;E>v;E-=1)if(this.clear(A,u[E])){S=E;break}A=u[S],b.push(A),v=S+1}return b}};var fe={x:0,z:-2.3,width:3.4},qn={x:-3.6,z:2.6},ws={z:-1,length:3.2},Ts={x:4.6,z:4.4},js={x:fe.x,z:fe.z-.75,face:{x:fe.x,z:6},sit:!0},W_=i=>({x:fe.x-1+i*1,z:fe.z+.85,face:{x:fe.x-1+i*1,z:-9},sit:!1}),X_=i=>({x:qn.x-1.1+i*.75,z:qn.z-.1,face:{x:qn.x-1.1+i*.75,z:-9},sit:!0}),hf=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Wn(r),l=Li("stone",r,Gt,2.4);t.add(l.mesh);let o=new ee;Wr(o,r,{wall:r?"#4b5163":"#f3efe8",low:r?"#40465a":"#e5ddd0"},{x:3.2,width:3.2}),o.add(I(fe.width,1.05,.5,.04),a.wood,{x:fe.x,y:.525,z:fe.z+.1},"satin"),o.add(I(fe.width+.1,.05,.62,.015),a.deskTop,{x:fe.x,y:1.07,z:fe.z+.1},"satin"),o.add(I(fe.width-.2,.7,.04),a.woodLight,{x:fe.x,y:.45,z:fe.z+.37},"satin",!1),o.add(I(.64,.4,.035,.014),"#1d2027",{x:fe.x+.6,y:1.32,z:fe.z},"satin"),o.add(I(.5,.04,.35,.01),a.metal,{x:fe.x-1.2,y:1.11,z:fe.z+.1},"metal"),o.add(I(.46,.07,.44,.03),a.seat,{x:js.x,y:.29,z:js.z},"matte"),o.add(I(.44,.46,.06,.03),a.chair,{x:js.x,y:.62,z:js.z-.23},"matte"),o.add(Ot(.025,.025,.2,10),"#5d6470",{x:js.x,y:.16,z:js.z},"metal"),o.add(I(2,.5,.05,.02),r?"#2b2f38":"#e9e4dc",{x:fe.x-.4,y:1.95,z:Gt.z0+.03},"satin",!1),o.add(I(1.8,.08,.02),n.accent,{x:fe.x-.4,y:1.95,z:Gt.z0+.06},"glow",!1),o.add(I(.04,1.3,ws.length+.08,.012),"#aeb5bf",{x:Gt.x0+.04,y:1.55,z:ws.z},"metal",!1),o.add(I(.02,1.2,ws.length),r?"#26303a":"#fcfcfa",{x:Gt.x0+.07,y:1.55,z:ws.z},"satin",!1),o.add(I(3.2,.08,.5,.03),a.seat,{x:qn.x,y:.45,z:qn.z},"matte"),o.add(I(3.2,.5,.08,.03),a.seat,{x:qn.x,y:.72,z:qn.z+.24},"matte");for(let u of[-1.45,0,1.45])o.add(I(.06,.45,.4),a.metal,{x:qn.x+u,y:.22,z:qn.z},"metal",!1);o.add(I(.08,2.3,.08),a.metal,{x:Ts.x-.8,y:1.15,z:Ts.z},"metal"),o.add(I(.08,2.3,.08),a.metal,{x:Ts.x+.8,y:1.15,z:Ts.z},"metal"),o.add(I(1.68,.1,.1),a.metal,{x:Ts.x,y:2.3,z:Ts.z},"metal"),Ji(o,r,-5.4,4,!0),Ji(o,r,1.9,-3.9),t.add(cn(o,e));let c=new Me({color:"#0e1420",emissive:a.dim,emissiveIntensity:.35,roughness:.3}),h=new kt(I(.58,.34,.008),c);h.userData.shared=!0,h.position.set(fe.x+.6,1.32,fe.z-.02),h.rotation.y=Math.PI,t.add(h);let f=new se;t.add(f);let d=new kt(new ce(fe.width,1.1,.6),new be({visible:!1}));d.position.set(fe.x,.55,fe.z+.1),t.add(d),i.pickable(d,"route:settings");let p=new kt(new ce(.1,1.3,ws.length),new be({visible:!1}));p.position.set(Gt.x0+.06,1.55,ws.z),t.add(p),i.pickable(p,"route:settings");let x=-1,M=!1,m=!1;return{frame:{min:{x:Gt.x0,y:0,z:Gt.z0},max:{x:Gt.x1,y:2.5,z:Gt.z1},polar:.98,azimuth:.62},lamps:[{x:0,y:2.2,z:-1.6},{x:-3.6,y:2.2,z:2.2},{x:3.2,y:2.2,z:2}],floor:{grid:new ei([{x0:fe.x-fe.width/2,x1:fe.x+fe.width/2,z0:fe.z-.2,z1:fe.z+.4},{x0:qn.x-1.6,x1:qn.x+1.6,z0:qn.z,z1:qn.z+.3}]),door:{x:Ts.x,z:Ts.z-.2}},update({model:u,t:b}){M=u.enabled,m=u.error;let A=[];u.enabled&&A.push({id:"reception",name:b("places.desk.receptionist"),state:u.error?"failed":u.pairing?"waiting":u.outgoing>0?"working":"idle",stateLabel:u.error?b("places.desk.error"):u.pairing?b("places.desk.pairing"):u.outgoing>0?b("places.desk.sending",{count:u.outgoing}):u.running?b("places.desk.open"):b("places.desk.starting"),look:zi("legal"),place:js,action:u.error?"slump":u.pairing?"raise":u.outgoing>0?"talk":"rest",...u.pairing?{bubble:"\u2026"}:u.error?{bubble:"!"}:{},pick:"route:settings"});let v=0,S=0;for(let R of u.phones){if(!R.online&&!R.recent)continue;let g=R.recent!==null&&v<3;A.push({id:`phone-${R.id}`,name:R.name,state:g?"working":"idle",stateLabel:b(g?`places.desk.action.${R.recent}`:"places.desk.waiting"),look:zi(`phone:${R.id}`),place:g?W_(v++):X_(S++%4),action:g?"talk":"rest",pick:"route:settings"})}if(x!==Math.min(4,u.outgoing)){x=Math.min(4,u.outgoing);for(let g of[...f.children])g.removeFromParent(),An(g);let R=new ee;for(let g=0;g<x;g+=1)R.add(I(.3,.14,.22,.015),"#c9a47a",{x:fe.x-1.2+g%2*.05,y:1.2+g*.15,z:fe.z+.1,ry:g*.3},"matte"),R.add(I(.31,.02,.05),n.accent,{x:fe.x-1.2+g%2*.05,y:1.2+g*.15+.07,z:fe.z+.1,ry:g*.3},"satin",!1);x>0&&f.add(cn(R,e))}let E={};return u.phones.slice(0,6).forEach((R,g)=>{E[`badge-${R.id}`]={at:{x:Gt.x0+.1,y:2.05-g*.2,z:ws.z},title:R.name,detail:R.online?b("places.desk.online"):b("places.desk.offline"),...R.online?{tone:"busy"}:{},pick:"route:settings"}}),u.phones.length===0&&(E.none={at:{x:Gt.x0+.1,y:1.7,z:ws.z},title:b("places.desk.noPhones"),pick:"route:settings"}),u.enabled||(E.closed={at:{x:fe.x,y:1.5,z:fe.z},title:b("places.desk.closed"),detail:b("places.desk.closedHint"),pick:"route:settings"}),{people:A,labels:E}},tick(u){return c.emissive.set(m?"#8a2b24":M?r?"#3d7bd9":"#4b8fe6":a.dim),c.emissiveIntensity=M?.75+(s?0:Math.sin(u*2)*.05):.2,!1},dispose(){l.dispose();for(let u of[...t.children])An(u);c.dispose();for(let u of[d,p])u.material.dispose()}}};var ni=i=>({x:-4.2+i%4*2.8,z:i<4?-1.5:1.6}),mi={x:-2.4,y:1.75},Ga={x:2.2,width:3.2},q_=i=>{let{x:t,z:e}=ni(i);return{x:t,z:e-.75,face:{x:t,z:e+2},sit:!0}},Y_=i=>{let{x:t,z:e}=ni(i);return{x:t+.85,z:e-.6,face:{x:mi.x,z:-9},sit:!1}},Z_={running:"type",soon:"rest",idle:"rest",failed:"slump",done:"rest",off:"rest"},uf=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Wn(r),l=Li("carpet",r,Gt,2);t.add(l.mesh);let o=new ee;Wr(o,r),o.add(Ot(.55,.55,.05,40),"#fbfaf7",{x:mi.x,y:mi.y,z:Gt.z0+.05,rx:Math.PI/2},"satin",!1),o.add(gn(.55,.04,Math.PI*2,6,40),"#3b3b40",{x:mi.x,y:mi.y,z:Gt.z0+.07},"metal",!1);for(let u=0;u<12;u+=1){let b=u/12*Math.PI*2;o.add(I(.03,u%3===0?.1:.06,.01),"#3b3b40",{x:mi.x+Math.sin(b)*.44,y:mi.y+Math.cos(b)*.44,z:Gt.z0+.08,rz:-b},"matte",!1)}o.add(I(Ga.width+.08,1.3,.04,.012),"#aeb5bf",{x:Ga.x,y:1.65,z:Gt.z0+.03},"metal",!1),o.add(I(Ga.width,1.2,.02),r?"#26303a":"#fcfcfa",{x:Ga.x,y:1.65,z:Gt.z0+.055},"satin",!1);let c=Array.from({length:8},(u,b)=>Zl(o,r,ni(b).x,ni(b).z));o.add(I(1.2,.85,.5,.02),a.wood,{x:-5,y:.42,z:3.9},"satin"),o.add(I(.3,.36,.26,.03),"#2b2e36",{x:-5.2,y:1.03,z:3.9},"metal");for(let u of[.1,.25])o.add(Ot(.045,.04,.1,14),"#fbfaf7",{x:-5+u,y:.9,z:3.9},"satin",!1);Ji(o,r,5.4,3.9,!0),Ji(o,r,5.5,-4),t.add(cn(o,e));let h=new Me({color:"#25252a",roughness:.5}),f=new ce(.05,.3,.015).translate(0,.13,0),d=new ce(.035,.45,.015).translate(0,.2,0),p=new kt(f,h),x=new kt(d,h);p.position.set(mi.x,mi.y,Gt.z0+.1),x.position.set(mi.x,mi.y,Gt.z0+.11),t.add(p,x);let M=c.map(u=>{let b=new Me({color:"#0e1420",emissive:a.dim,emissiveIntensity:.3,roughness:.3}),A=new kt(I(.58,.34,.008),b);return A.userData.shared=!0,A.position.copy(u),t.add(A),b});for(let u=0;u<8;u+=1){let b=new kt(new ce(1.2,1.1,1.5),new be({visible:!1}));b.position.set(ni(u).x,.55,ni(u).z-.35),t.add(b),i.pickable(b,"route:schedules")}let m=[];return{frame:{min:{x:Gt.x0,y:0,z:Gt.z0},max:{x:Gt.x1,y:2.4,z:Gt.z1},polar:.98,azimuth:.62},lamps:[{x:-2.8,y:2.2,z:-1.6},{x:2.8,y:2.2,z:-1.6},{x:-2.8,y:2.2,z:1.6},{x:2.8,y:2.2,z:1.6}],floor:{grid:new ei([...Array.from({length:8},(u,b)=>({x0:ni(b).x-.6,x1:ni(b).x+.6,z0:ni(b).z-.35,z1:ni(b).z+.35})),{x0:-5.6,x1:-4.4,z0:3.65,z1:4.15}]),door:{x:5.2,z:4.2}},update({model:u,t:b}){m=u.officers;let A=m.flatMap((S,E)=>S.state==="off"?[]:[{id:S.id,name:S.title||b("places.duty.untitled"),state:S.state==="running"?"working":S.state==="failed"?"failed":S.state==="done"?"done":S.state==="soon"?"waiting":"idle",stateLabel:b(`places.duty.state.${S.state}`),look:zi(`schedule:${S.id}`),place:S.state==="soon"?Y_(E):q_(E),action:Z_[S.state],...S.state==="failed"?{bubble:"!"}:S.state==="done"?{bubble:"\u2713"}:{},pick:"route:schedules"}]),v={};return m.forEach((S,E)=>{S.state==="off"&&(v[`off-${S.id}`]={at:{x:ni(E).x,y:1.3,z:ni(E).z},title:S.title||b("places.duty.untitled"),detail:b("places.duty.state.off"),pick:"route:schedules"})}),u.upcoming.slice(0,4).forEach((S,E)=>{let R=new Date(S.at),g=Number.isNaN(R.getTime())?S.at:R.toLocaleString(void 0,{weekday:"short",hour:"2-digit",minute:"2-digit"});v[`next-${S.id}`]={at:{x:Ga.x,y:2.15-E*.28,z:Gt.z0+.1},title:g,detail:S.title,pick:"route:schedules"}}),m.length===0&&(v.empty={at:{x:0,y:1.3,z:0},title:b("places.duty.empty"),pick:"route:schedules"}),u.more>0&&(v.more={at:{x:4.6,y:1,z:3.2},title:b("places.duty.more",{count:u.more})}),{people:A,labels:v}},tick(u){let b=new Date;return x.rotation.z=-((b.getMinutes()+b.getSeconds()/60)/60)*Math.PI*2,p.rotation.z=-((b.getHours()%12+b.getMinutes()/60)/12)*Math.PI*2,M.forEach((A,v)=>{let S=m[v],E=S?.state==="running";A.emissive.set(E?r?"#3d7bd9":"#4b8fe6":S?.state==="failed"?"#8a2b24":a.dim),A.emissiveIntensity=E?.9+(s?0:Math.sin(u*7+v)*.08):S&&S.state!=="off"?.45:.15}),!1},dispose(){l.dispose();for(let u of[...t.children])An(u);h.dispose();for(let u of M)u.dispose();t.traverse(u=>{u instanceof kt&&u.material instanceof be&&!u.material.visible&&u.material.dispose()})}}};var Ui=1.9,Rn=2.2,Qs=.42,Oh=4,jl=.52,Bh=[2,1,3,0],Fi=i=>-4.6+i*2.3,gi=Gt.z0+Qs/2+.04,Ue={x:Gt.x0+.24,z0:-2.6,z1:.6},ii=[{x:-1.3,z:.9},{x:2.1,z:.9}],xi={x:3.9,z:3.3},en={x:1.9,z:3.5},_i={x:5.3,z:1.6},kh={pdf:"#b5523b",word:"#3d6fa5",sheet:"#4f8a5b",slides:"#e0a13a",web:"#7b5ea7",text:"#c06c84",image:"#2f4858",other:"#8a8d3b"},ff=i=>({x:Fi(i),z:gi+.85,face:{x:Fi(i),z:-9},sit:!1}),pf={x:Ue.x+.75,z:(Ue.z0+Ue.z1)/2,face:{x:-9,z:(Ue.z0+Ue.z1)/2},sit:!1},$_={x:ii[0].x-.5,z:ii[0].z-.72,face:{x:ii[0].x-.5,z:5},sit:!0},K_={x:xi.x,z:xi.z-.75,face:{x:xi.x,z:6},sit:!0},J_={x:en.x,z:en.z-.65,face:{x:en.x,z:6},sit:!1},j_={x:_i.x-.7,z:_i.z,face:{x:9,z:_i.z},sit:!1},mf=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Wn(r),l=Li("wood",r,Gt,3);t.add(l.mesh);let o=new ee;Wr(o,r,{wall:r?"#4a4f5f":"#efe6d8",low:r?"#3f4454":"#e2d5c2"});for(let z=0;z<5;z+=1){let q=Fi(z);for(let N of[-1,1])o.add(I(.05,Rn,Qs,.01),a.wood,{x:q+N*(Ui/2),y:Rn/2,z:gi},"satin");o.add(I(Ui,Rn,.03),a.woodLight,{x:q,y:Rn/2,z:gi-Qs/2+.015},"matte",!1);for(let N=0;N<=Oh;N+=1)o.add(I(Ui,.035,Qs,.008),a.wood,{x:q,y:.06+N*jl,z:gi},"satin");o.add(I(Ui+.1,.08,Qs+.06,.02),a.wood,{x:q,y:Rn+.04,z:gi},"satin")}let c=Ue.z1-Ue.z0;for(let z of[Ue.z0,Ue.z1])o.add(I(.42,Rn,.05,.01),a.wood,{x:Ue.x,y:Rn/2,z},"satin");for(let z=0;z<=Oh;z+=1)o.add(I(.42,.035,c,.008),a.wood,{x:Ue.x,y:.06+z*jl,z:(Ue.z0+Ue.z1)/2},"satin");for(let z of ii){o.add(I(2.4,.06,.95,.02),a.wood,{x:z.x,y:.72,z:z.z},"satin");for(let[q,N]of[[-1.1,-.38],[1.1,-.38],[-1.1,.38],[1.1,.38]])o.add(I(.07,.7,.07),a.woodLight,{x:z.x+q,y:.35,z:z.z+N},"satin");for(let q of[-.5,.5]){for(let N of[-1,1]){let G=z.z+N*.72;o.add(I(.42,.06,.4,.02),a.seat,{x:z.x+q,y:.46,z:G},"matte"),o.add(I(.42,.42,.05,.02),a.wood,{x:z.x+q,y:.7,z:G+N*.2},"satin");for(let[X,K]of[[-.17,-.15],[.17,-.15],[-.17,.15],[.17,.15]])o.add(I(.035,.44,.035),a.woodLight,{x:z.x+q+X,y:.22,z:G+K},"satin",!1)}o.add(Ot(.06,.07,.02,12),"#b08d3c",{x:z.x+q,y:.76,z:z.z},"metal",!1),o.add(Ot(.012,.012,.26,6),"#b08d3c",{x:z.x+q,y:.88,z:z.z},"metal",!1),o.add(I(.3,.07,.12,.03),"#2f6b48",{x:z.x+q,y:1.02,z:z.z},r?"glow":"satin",!1)}}let h=Zl(o,r,xi.x,xi.z,1.8);o.add(I(.9,.05,.5,.01),a.metal,{x:en.x,y:.75,z:en.z},"metal"),o.add(I(.9,.05,.5,.01),a.metal,{x:en.x,y:.35,z:en.z},"metal");for(let[z,q]of[[-.42,-.22],[.42,-.22],[-.42,.22],[.42,.22]])o.add(I(.03,.75,.03),a.metal,{x:en.x+z,y:.42,z:en.z+q},"metal",!1),o.add(Ot(.04,.04,.03,10),"#2a2d35",{x:en.x+z,y:.04,z:en.z+q,rz:Math.PI/2},"satin",!1);o.add(I(.7,.9,.6,.03),r?"#c9ccd2":"#eef0f3",{x:_i.x,y:.45,z:_i.z},"satin"),o.add(I(.62,.04,.5,.01),"#3a3f4b",{x:_i.x,y:.92,z:_i.z},"satin",!1),Ji(o,r,-5.4,4,!0),Ji(o,r,5.5,-2.9),t.add(cn(o,e));let f=430,d=new Me({roughness:.8}),p=new hi(new ce(1,1,1),d,f);p.castShadow=!0,p.count=0,t.add(p);let x=new be({color:n.accent,toneMapped:!1}),M=new hi(new ce(1,1,1),x,360);M.count=0,t.add(M);let m=new se;t.add(m);let u=new Ti("#ffd9a0",0,3,1.6);u.position.set(ii[0].x-.5,1.2,ii[0].z),t.add(u);let b=new Me({color:"#0e1420",emissive:a.dim,emissiveIntensity:.4,roughness:.3}),A=new kt(I(.58,.34,.008),b);A.userData.shared=!0,A.position.copy(h),t.add(A);for(let z=0;z<5;z+=1){let q=new kt(new ce(Ui,Rn,Qs),new be({visible:!1}));q.position.set(Fi(z),Rn/2,gi),t.add(q),i.pickable(q,"route:knowledge")}let v=new kt(new ce(.42,Rn,c),new be({visible:!1}));v.position.set(Ue.x,Rn/2,(Ue.z0+Ue.z1)/2),t.add(v),i.pickable(v,"route:workspace");let S=new ge,E=new $t,R=new Ye,g=new Ln,w=(z,q,N,G,X,K,nt,tt,lt=0)=>{R.setFromEuler(g.set(0,0,lt)),S.compose(new F(q,N,G),R,new F(X,K,nt)),p.setMatrixAt(z,S),p.setColorAt(z,E.set(tt))},T=z=>.045+Math.min(.06,Math.log2(1+z.size)*.008),C=z=>{let q=0,N=0;z.cases.forEach((K,nt)=>{let tt=0,lt=Bh[0],zt=Fi(nt)-Ui/2+.08;for(let Lt of K.books){let gt=T(Lt);if(zt+gt>Fi(nt)+Ui/2-.06){if(tt+=1,tt>=Bh.length)break;lt=Bh[tt],zt=Fi(nt)-Ui/2+.08}let J=.36+zh(Lt.id)*.1,et=.08+lt*jl+J/2,pt=Lt.cited?.08:0;w(q++,zt+gt/2,et,gi+.02+pt,gt,J,.24,kh[Lt.kind]),Lt.cited&&(S.compose(new F(zt+gt/2,et+J/2+.03,gi+.14+pt),R.identity(),new F(Math.max(.012,gt*.4),.08,.01)),M.setMatrixAt(N++,S)),zt+=gt+.006}});let G=Oh-1,X=Ue.z0+.06;for(let K of z.papers.books){if(X+.03>Ue.z1-.06&&(G-=1,X=Ue.z0+.06,G<0))break;w(q++,Ue.x+.04,.08+G*jl+.15,X+.012,.25,.3,.024,zh(K.id)>.5?"#e8e2d2":"#d9cdb4"),X+=.03}return z.cart.forEach((K,nt)=>{let tt=K.state==="failed",lt=en.x-.36+nt%5*.17,zt=nt<5?.79:.39;w(q++,lt,zt+(tt?.02:.13),en.z,tt?.24:.05,tt?.04:.26,tt?.18:.2,tt?"#8a8f98":new $t(kh[K.kind]).lerp(new $t("#ffffff"),.35).getStyle())}),p.count=q,M.count=N,p.instanceMatrix.needsUpdate=!0,p.instanceColor&&(p.instanceColor.needsUpdate=!0),M.instanceMatrix.needsUpdate=!0,N},D=!1,V=!1,U=0;return{frame:{min:{x:Gt.x0,y:0,z:Gt.z0},max:{x:Gt.x1,y:Rn+.2,z:Gt.z1},polar:.98,azimuth:.62},lamps:[{x:-2.3,y:2.2,z:-2.6},{x:2.3,y:2.2,z:-2.6},{x:.4,y:2,z:1},{x:3.9,y:1.9,z:3}],floor:{grid:new ei([...Array.from({length:5},(z,q)=>({x0:Fi(q)-Ui/2,x1:Fi(q)+Ui/2,z0:Gt.z0,z1:gi+Qs/2})),{x0:Gt.x0,x1:Ue.x+.21,z0:Ue.z0,z1:Ue.z1},...ii.map(z=>({x0:z.x-1.2,x1:z.x+1.2,z0:z.z-.48,z1:z.z+.48})),{x0:xi.x-.9,x1:xi.x+.9,z0:xi.z-.35,z1:xi.z+.35},{x0:en.x-.45,x1:en.x+.45,z0:en.z-.25,z1:en.z+.25},{x0:_i.x-.35,x1:_i.x+.35,z0:_i.z-.3,z1:_i.z+.3}]),door:{x:5.4,z:4.2}},update({model:z,t:q,lead:N,visitors:G=[]}){C(z);let X=[],{librarian:K}=z,nt=z.cases.findIndex(gt=>gt.id===K.caseId),tt=K.state==="searching"?ff(Math.max(0,nt)):K.state==="papers"?pf:K.state==="reading"?$_:K.state==="adding"?J_:K_;X.push({id:"librarian",name:N,state:K.state==="idle"?"idle":"working",stateLabel:q(`places.library.librarian.${K.state}`),look:zi("lead"),place:tt,action:K.state==="searching"||K.state==="papers"?"read":K.state==="reading"?"paper":K.state==="adding"?"operate":"rest",pick:"agent"}),z.clerk&&X.push({id:"clerk",name:q("places.library.clerk"),state:"working",stateLabel:q("places.library.reading",{count:z.cart.filter(gt=>gt.state!=="failed").length}),look:zi("teacher"),place:j_,action:"operate",pick:"route:knowledge"});let zt=[...Array.from({length:5},(gt,J)=>[ff(J),"read"]),[pf,"read"],...[-.5,.5].map(gt=>[{x:ii[1].x+gt,z:ii[1].z-.72,face:{x:ii[1].x+gt,z:5},sit:!0},"paper"])].filter(([gt])=>gt.x!==tt.x||gt.z!==tt.z);if(G.slice(0,zt.length).forEach((gt,J)=>{let[et,pt]=zt[J];X.push({id:gt.id,name:gt.name,state:"working",stateLabel:gt.stateLabel,look:gt.look,place:et,action:pt,pick:gt.pick})}),D=K.state==="reading",V=K.state!=="idle",U!==(D?Math.min(6,K.cited):0)){U=D?Math.min(6,K.cited):0;for(let J of[...m.children])J.removeFromParent(),An(J);let gt=new ee;for(let J=0;J<U;J+=1)gt.add(I(.24,.05,.3,.008),Object.values(kh)[J%8],{x:ii[0].x-.05,y:.775+J*.052,z:ii[0].z-.1,ry:J%3*.12},"matte");U>0&&m.add(cn(gt,e))}let Lt={};if(z.cases.forEach((gt,J)=>{Lt[`case-${gt.id}`]={at:{x:Fi(J),y:Rn+.25,z:gi},title:gt.name,detail:q("places.library.documents",{count:gt.total}),...K.caseId===gt.id&&K.state!=="idle"?{tone:"busy"}:{},pick:"route:knowledge"}}),z.cases.length===0&&(Lt.empty={at:{x:0,y:Rn+.25,z:gi},title:q("places.library.empty"),pick:"route:knowledge"}),z.papers.total>0&&(Lt.papers={at:{x:Ue.x,y:Rn+.25,z:(Ue.z0+Ue.z1)/2},title:q("places.library.papers"),detail:q("places.library.paperCount",{count:z.papers.total}),pick:"route:workspace"}),z.cart.length>0){let gt=z.cart.filter(J=>J.state==="failed").length;Lt.cart={at:{x:en.x,y:1.1,z:en.z},title:q("places.library.cart"),detail:gt>0?q("places.library.failed",{count:gt}):q("places.library.reading",{count:z.cart.length}),tone:gt>0?"alert":"busy",pick:"route:knowledge"}}return z.enabled||(Lt.off={at:{x:xi.x,y:1.4,z:xi.z},title:q("places.library.off"),tone:"alert",pick:"route:knowledge"}),{people:X,labels:Lt}},tick(z){return u.intensity+=((D?r?5:2:0)-u.intensity)*(s?1:.08),b.emissive.set(V?r?"#3d7bd9":"#4b8fe6":a.dim),b.emissiveIntensity=V?.9+(s?0:Math.sin(z*5)*.08):.35,!1},dispose(){l.dispose();for(let z of[...t.children])z!==p&&z!==M&&An(z);p.geometry.dispose(),M.geometry.dispose(),d.dispose(),x.dispose(),b.dispose(),u.dispose(),t.traverse(z=>{z instanceof kt&&z.material instanceof be&&!z.material.visible&&z.material.dispose()})}}};var $r={x0:-3.5,x1:4.1,z0:-2.7,z1:3.9},Ql=4,tc=.24,Rs=.36,Wa=.26,He={x:-4.85,z:-3.55},bn={x:4.9,z:-3.55},As={x:5.2,z:4.2},Hh=4.6,ty={code:"#5b7db1",web:"#7b5ea7",doc:"#e3dccb",data:"#4f8a5b",config:"#9aa1ab",asset:"#c06c84",other:"#b8a48c"},Vh={x:He.x+1.35,z:He.z+.5,face:{x:0,z:2},sit:!1};function ey(i){let t=i>Ql?2:1,e=Math.min(Ql,Math.max(1,i)),n=($r.x1-$r.x0-tc*(e-1))/e,s=($r.z1-$r.z0-tc*(t-1))/t;return Array.from({length:i},(r,a)=>{let l=a%Ql,o=Math.floor(a/Ql),c=$r.x0+l*(n+tc),h=$r.z0+o*(s+tc);return{x0:c,x1:c+n,z0:h,z1:h+s,columns:Math.max(1,Math.floor((n-.1)/Rs))}})}var gf=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Wn(r),l=Li("dirt",r,Gt,3);t.add(l.mesh);let o=new ee;o.add(I(Gt.x1-Gt.x0+.1,.12,Gt.z1-Gt.z0+.1),a.skirt,{y:-.3},"matte",!1);let c=r?"#8a93a3":"#9aa1ab";for(let tt=Gt.x0;tt<=Gt.x1+.01;tt+=1.2)o.add(Ot(.04,.04,1.3,8),c,{x:tt,y:.65,z:Gt.z0+.05},"metal");for(let tt=Gt.z0;tt<=Gt.z1+.01;tt+=1.2)o.add(Ot(.04,.04,1.3,8),c,{x:Gt.x0+.05,y:.65,z:tt},"metal");o.add(I(Gt.x1-Gt.x0,1.1,.02),r?"#3c4c5e":"#7d97b0",{y:.65,z:Gt.z0+.05},"glass",!1),o.add(I(.02,1.1,Gt.z1-Gt.z0),r?"#3c4c5e":"#7d97b0",{x:Gt.x0+.05,y:.65},"glass",!1);let h=r?"#c9a43a":"#e8c547";o.add(I(2.1,1.25,1.2,.03),h,{x:He.x,y:.8,z:He.z},"satin"),o.add(I(2.2,.08,1.3,.02),a.trim,{x:He.x,y:1.46,z:He.z},"satin");for(let tt of[-.85,.85])o.add(I(.3,.18,1),"#7a7a7a",{x:He.x+tt,y:.09,z:He.z},"matte");o.add(I(.7,.45,.02),a.sky,{x:He.x-.35,y:.95,z:He.z+.61},"glow",!1),o.add(I(.4,.95,.02),"#5d6470",{x:He.x+.6,y:.66,z:He.z+.61},"satin",!1),o.add(I(.5,.08,.3),"#7a7a7a",{x:He.x+.6,y:.1,z:He.z+.78},"matte"),o.add(I(.9,.3,.9,.02),"#7a7a7a",{x:bn.x,y:.15,z:bn.z},"matte");for(let tt=.3;tt<Hh;tt+=.45){for(let[lt,zt]of[[-.18,-.18],[.18,-.18],[-.18,.18],[.18,.18]])o.add(I(.04,.46,.04),"#e0a13a",{x:bn.x+lt,y:tt+.22,z:bn.z+zt},"metal",!1);o.add(I(.4,.03,.4),"#e0a13a",{x:bn.x,y:tt,z:bn.z},"metal",!1)}t.add(cn(o,e));let f=new se;f.position.set(bn.x,Hh,bn.z);let d=new ee;d.add(I(7.2,.18,.22),"#e0a13a",{x:-2.8},"metal"),d.add(I(1.4,.3,.5,.03),"#6b7280",{x:1.2,y:-.1},"metal"),d.add(I(.7,.55,.55,.03),r?"#c9ccd2":"#eef0f3",{x:.2,y:-.4},"satin"),f.add(cn(d,e));let p=new se,x=new ee;x.add(Ot(.008,.008,1,4),"#2a2d35",{y:-.5},"metal",!1),p.add(cn(x,e)),f.add(p);let M=new se,m=new ee;m.add(I(.1,.12,.1,.02),"#2a2d35",{},"metal"),M.add(cn(m,e)),f.add(M),t.add(f);let u=240,b=new Me({roughness:.7}),A=new hi(new ce(1,1,1).translate(0,.5,0),b,u);A.castShadow=!0,A.receiveShadow=!0,A.count=0,t.add(A);let v=new Me({color:"#f08a24",transparent:!0,opacity:.38,roughness:.6,depthWrite:!1}),S=new hi(new ce(1,1,1).translate(0,.5,0),v,u);S.count=0,t.add(S);let E=new se;t.add(E);let R=new se;t.add(R);let g=new be({color:"#ff3b30",toneMapped:!1}),w=new kt(I(.12,.12,.12,.03),g);w.userData.shared=!0,w.position.set(He.x-.85,1.6,He.z+.4),t.add(w);let T=[];i.pickable(A,tt=>T[tt]?`file:${T[tt].path}`:void 0);let C=new kt(new ce(2.1,1.5,1.2),new be({visible:!1}));C.position.set(He.x,.8,He.z),t.add(C),i.pickable(C,"route:changes");let D=new ge,V=new $t,U=new Map,z=null,q=.4,N=!1,G="",X="",K=tt=>{let lt=ey(Math.min(8,tt.districts.length)),zt=lt.map(et=>`${et.x0.toFixed(2)},${et.z0.toFixed(2)}`).join("|");if(zt!==G){G=zt;for(let pt of[...E.children])pt.removeFromParent(),An(pt);let et=new ee;for(let pt of lt)et.add(I(pt.x1-pt.x0,.04,pt.z1-pt.z0,.01),r?"#4a4f5a":"#d6d2c8",{x:(pt.x0+pt.x1)/2,y:.02,z:(pt.z0+pt.z1)/2},"matte",!1);lt.length>0&&E.add(cn(et,e))}let Lt=0,gt=0;T=[],U.clear(),z=null;let J={};return tt.districts.forEach((et,pt)=>{let At=lt[pt];if(!At)return;let Mt=Math.max(1,Math.floor((At.z1-At.z0-.1)/Rs)),qt=Math.min(At.columns,Math.max(1,Math.ceil(et.buildings.length/Mt),Math.ceil(Math.sqrt(et.buildings.length*(At.x1-At.x0)/(At.z1-At.z0))))),ve=Math.min(Mt,Math.ceil(et.buildings.length/qt)),Jt=At.x0+(At.x1-At.x0-qt*Rs)/2,te=At.z0+(At.z1-At.z0-ve*Rs)/2;et.buildings.forEach((ne,jt)=>{let xe=jt%qt,ze=Math.floor(jt/qt),Ie=Jt+Rs/2+xe*Rs,pe=te+Rs/2+ze*Rs;if(pe+Wa/2>At.z1||Lt>=u)return;let _e=.12+ne.height*1.5;D.compose(new F(Ie,.04,pe),new Ye,new F(Wa,_e,Wa)),A.setMatrixAt(Lt,D),A.setColorAt(Lt,V.set(ne.editing?n.accent:ty[ne.kind])),T[Lt]=ne,Lt+=1,U.set(ne.path,new F(Ie,_e,pe)),ne.editing&&(z=new F(Ie,_e,pe)),(ne.changed||ne.conflict||ne.editing)&&(D.compose(new F(Ie,.04,pe),new Ye,new F(Wa+.07,_e+.12,Wa+.07)),S.setMatrixAt(gt,D),S.setColorAt(gt,V.set(ne.conflict?"#e5534b":"#ffffff")),gt+=1)}),J[`district-${et.name}`]={at:{x:(At.x0+At.x1)/2,y:.5,z:At.z1},title:et.name==="."?tt.folder??".":et.name,detail:String(et.total)}}),A.count=Lt,S.count=gt,A.instanceMatrix.needsUpdate=!0,A.instanceColor&&(A.instanceColor.needsUpdate=!0),S.instanceMatrix.needsUpdate=!0,S.instanceColor&&(S.instanceColor.needsUpdate=!0),J},nt=tt=>{if(R.children.length===tt)return;for(let zt of[...R.children])zt.removeFromParent(),An(zt);let lt=new ee;for(let zt=0;zt<tt;zt+=1){let Lt=As.z-.9-zt*1.25;lt.add(I(.75,.6,1,.04),"#f2f2f2",{x:As.x,y:.45,z:Lt},"satin"),lt.add(I(.7,.5,.42,.05),"#3f88c5",{x:As.x,y:.4,z:Lt+.72},"satin"),lt.add(I(.6,.18,.02),a.sky,{x:As.x,y:.52,z:Lt+.94},"glow",!1);for(let[gt,J]of[[-.38,-.3],[.38,-.3],[-.38,.7],[.38,.7]])lt.add(Ot(.12,.12,.08,12),"#1d2027",{x:As.x+gt,y:.12,z:Lt+J,rz:Math.PI/2},"satin")}tt>0&&R.add(cn(lt,e))};return{frame:{min:{x:Gt.x0,y:0,z:Gt.z0},max:{x:Gt.x1,y:2.2,z:Gt.z1},polar:.92,azimuth:.62},lamps:[{x:-4.5,y:3,z:-3,colour:"#fff1d6"},{x:2,y:3,z:-3.6,colour:"#fff1d6"},{x:.5,y:3,z:2.5,colour:"#fff1d6"}],floor:{grid:new ei([{x0:He.x-1.05,x1:He.x+1.05,z0:He.z-.6,z1:He.z+.6},{x0:bn.x-.45,x1:bn.x+.45,z0:bn.z-.45,z1:bn.z+.45}]),door:As},update({model:tt,t:lt,lead:zt,visitors:Lt=[]}){X=lt("places.site.uncommitted");let gt=K(tt);nt(Math.min(3,tt.ahead)),N=tt.checks.failed.length>0;let J=z,et=J&&tt.worker.state==="editing"?{x:J.x-.32,z:J.z+.32,face:{x:J.x,z:J.z},sit:!1}:Vh,pt=[{id:"worker",name:zt,state:tt.worker.state==="idle"?"idle":"working",stateLabel:lt(`places.site.worker.${tt.worker.state}`),look:{...zi("lead"),accessory:"helmet"},place:et,action:tt.worker.state==="editing"||tt.worker.state==="testing"?"operate":tt.worker.state==="reading"?"paper":tt.worker.state==="thinking"?"think":"rest",pick:"agent"}],At=[...U.values()];return Lt.forEach((Mt,qt)=>{let ve=At.length>0?At[(qt*7+3)%At.length]:new F(Vh.x+.6*(qt+1),0,Vh.z+.4);pt.push({id:Mt.id,name:Mt.name,state:"working",stateLabel:Mt.stateLabel,look:{...Mt.look,accessory:"helmet"},place:{x:ve.x+.3,z:ve.z+.3,face:{x:ve.x,z:ve.z},sit:!1},action:"operate",pick:Mt.pick})}),gt.office={at:{x:He.x,y:1.75,z:He.z},title:tt.branch??lt("places.site.noGit"),detail:tt.checks.running?lt("places.site.checking"):tt.checks.failed.length>0?lt("places.site.checksFailed",{names:tt.checks.failed.slice(0,3).join(", ")}):tt.changed>0?lt("places.site.changed",{count:tt.changed}):lt("places.site.clean"),...tt.checks.failed.length>0?{tone:"alert"}:tt.checks.running||tt.worker.state!=="idle"?{tone:"busy"}:{},pick:"route:changes"},tt.ahead>0&&(gt.gate={at:{x:As.x,y:1,z:As.z-1.2},title:lt("places.site.unpushed",{count:tt.ahead}),pick:"route:changes"}),tt.files===0&&(gt.empty={at:{x:.3,y:.6,z:.6},title:lt("places.site.empty")}),{people:pt,labels:gt}},tick(tt,lt){let zt=z,gt=(zt?Math.atan2(-(zt.z-bn.z),zt.x-bn.x)+Math.PI:.4)-q;gt=Math.atan2(Math.sin(gt),Math.cos(gt));let J=Math.abs(gt)>.002;q+=s?gt:gt*Math.min(1,lt*1.5),f.rotation.y=q;let et=zt?Math.min(6.5,Math.hypot(zt.x-bn.x,zt.z-bn.z)):3,pt=Math.max(.3,zt?Hh-zt.y-.4:1.8);return p.position.set(-et,0,0),p.scale.set(1,pt,1),M.position.set(-et,-pt-.06,0),g.color.set(N?s||Math.sin(tt*6)>0?"#ff3b30":"#5a1a16":"#3a3f4b"),J},hover(tt){if(!tt.startsWith("file:"))return null;let lt=tt.slice(5),zt=U.get(lt),Lt=T.find(gt=>gt.path===lt);return zt&&Lt?{at:{x:zt.x,y:zt.y+.15,z:zt.z},title:lt,...Lt.changed?{detail:X,tone:"busy"}:{}}:null},dispose(){l.dispose();for(let tt of[...t.children])tt!==A&&tt!==S&&An(tt);A.geometry.dispose(),S.geometry.dispose(),b.dispose(),v.dispose(),g.dispose(),C.material.dispose()}}};var xf={type:"change"},Wh={type:"start"},yf={type:"end"},ec=new ks,_f=new Hn,ny=Math.cos(70*ln.DEG2RAD),nn=new F,Un=2*Math.PI,Re={NONE:-1,ROTATE:0,DOLLY:1,PAN:2,TOUCH_ROTATE:3,TOUCH_PAN:4,TOUCH_DOLLY_PAN:5,TOUCH_DOLLY_ROTATE:6},Gh=1e-6,Kr=class extends Ta{constructor(t,e=null){super(t,e),this.state=Re.NONE,this.target=new F,this.cursor=new F,this.minDistance=0,this.maxDistance=1/0,this.minZoom=0,this.maxZoom=1/0,this.minTargetRadius=0,this.maxTargetRadius=1/0,this.minPolarAngle=0,this.maxPolarAngle=Math.PI,this.minAzimuthAngle=-1/0,this.maxAzimuthAngle=1/0,this.enableDamping=!1,this.dampingFactor=.05,this.enableZoom=!0,this.zoomSpeed=1,this.enableRotate=!0,this.rotateSpeed=1,this.keyRotateSpeed=1,this.enablePan=!0,this.panSpeed=1,this.screenSpacePanning=!0,this.keyPanSpeed=7,this.zoomToCursor=!1,this.autoRotate=!1,this.autoRotateSpeed=2,this.keys={LEFT:"ArrowLeft",UP:"ArrowUp",RIGHT:"ArrowRight",BOTTOM:"ArrowDown"},this.mouseButtons={LEFT:_s.ROTATE,MIDDLE:_s.DOLLY,RIGHT:_s.PAN},this.touches={ONE:ys.ROTATE,TWO:ys.DOLLY_PAN},this.target0=this.target.clone(),this.position0=this.object.position.clone(),this.zoom0=this.object.zoom,this._cursorStyle="auto",this._domElementKeyEvents=null,this._lastPosition=new F,this._lastQuaternion=new Ye,this._lastTargetPosition=new F,this._quat=new Ye().setFromUnitVectors(t.up,new F(0,1,0)),this._quatInverse=this._quat.clone().invert(),this._spherical=new zn,this._sphericalDelta=new zn,this._scale=1,this._panOffset=new F,this._rotateStart=new Xt,this._rotateEnd=new Xt,this._rotateDelta=new Xt,this._panStart=new Xt,this._panEnd=new Xt,this._panDelta=new Xt,this._dollyStart=new Xt,this._dollyEnd=new Xt,this._dollyDelta=new Xt,this._dollyDirection=new F,this._mouse=new Xt,this._performCursorZoom=!1,this._pointers=[],this._pointerPositions={},this._controlActive=!1,this._onPointerMove=sy.bind(this),this._onPointerDown=iy.bind(this),this._onPointerUp=ry.bind(this),this._onContextMenu=dy.bind(this),this._onMouseWheel=ly.bind(this),this._onKeyDown=cy.bind(this),this._onTouchStart=hy.bind(this),this._onTouchMove=uy.bind(this),this._onMouseDown=ay.bind(this),this._onMouseMove=oy.bind(this),this._interceptControlDown=fy.bind(this),this._interceptControlUp=py.bind(this),this.domElement!==null&&this.connect(this.domElement),this.update()}set cursorStyle(t){this._cursorStyle=t,t==="grab"?this.domElement.style.cursor="grab":this.domElement.style.cursor="auto"}get cursorStyle(){return this._cursorStyle}connect(t){super.connect(t),this.domElement.addEventListener("pointerdown",this._onPointerDown),this.domElement.addEventListener("pointercancel",this._onPointerUp),this.domElement.addEventListener("contextmenu",this._onContextMenu),this.domElement.addEventListener("wheel",this._onMouseWheel,{passive:!1}),this.domElement.getRootNode().addEventListener("keydown",this._interceptControlDown,{passive:!0,capture:!0}),this.domElement.style.touchAction="none"}disconnect(){this.state=Re.NONE,this.domElement.removeEventListener("pointerdown",this._onPointerDown),this.domElement.ownerDocument.removeEventListener("pointermove",this._onPointerMove),this.domElement.ownerDocument.removeEventListener("pointerup",this._onPointerUp),this.domElement.removeEventListener("pointercancel",this._onPointerUp),this.domElement.removeEventListener("wheel",this._onMouseWheel),this.domElement.removeEventListener("contextmenu",this._onContextMenu),this.stopListenToKeyEvents();let t=this.domElement.getRootNode();t.removeEventListener("keydown",this._interceptControlDown,{capture:!0}),t.removeEventListener("keyup",this._interceptControlUp,{capture:!0}),this._controlActive=!1,this._pointers.length=0,this._pointerPositions={},this.domElement.style.touchAction="",this.domElement.style.cursor="auto"}dispose(){this.disconnect()}getPolarAngle(){return this._spherical.phi}getAzimuthalAngle(){return this._spherical.theta}getDistance(){return this.object.position.distanceTo(this.target)}listenToKeyEvents(t){t.addEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=t}stopListenToKeyEvents(){this._domElementKeyEvents!==null&&(this._domElementKeyEvents.removeEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=null)}saveState(){this.target0.copy(this.target),this.position0.copy(this.object.position),this.zoom0=this.object.zoom}reset(){this.target.copy(this.target0),this.object.position.copy(this.position0),this.object.zoom=this.zoom0,this.object.updateProjectionMatrix(),this.dispatchEvent(xf),this.update(),this.state=Re.NONE}pan(t,e){this._pan(t,e),this.update()}dollyIn(t){this._dollyIn(t),this.update()}dollyOut(t){this._dollyOut(t),this.update()}rotateLeft(t){this._rotateLeft(t),this.update()}rotateUp(t){this._rotateUp(t),this.update()}update(t=null){let e=this.object.position;nn.copy(e).sub(this.target),nn.applyQuaternion(this._quat),this._spherical.setFromVector3(nn),this.autoRotate&&this.state===Re.NONE&&this._rotateLeft(this._getAutoRotationAngle(t)),this.enableDamping?(this._spherical.theta+=this._sphericalDelta.theta*this.dampingFactor,this._spherical.phi+=this._sphericalDelta.phi*this.dampingFactor):(this._spherical.theta+=this._sphericalDelta.theta,this._spherical.phi+=this._sphericalDelta.phi);let n=this.minAzimuthAngle,s=this.maxAzimuthAngle;isFinite(n)&&isFinite(s)&&(n<-Math.PI?n+=Un:n>Math.PI&&(n-=Un),s<-Math.PI?s+=Un:s>Math.PI&&(s-=Un),n<=s?this._spherical.theta=Math.max(n,Math.min(s,this._spherical.theta)):this._spherical.theta=this._spherical.theta>(n+s)/2?Math.max(n,this._spherical.theta):Math.min(s,this._spherical.theta)),this._spherical.phi=Math.max(this.minPolarAngle,Math.min(this.maxPolarAngle,this._spherical.phi)),this._spherical.makeSafe(),this.enableDamping===!0?this.target.addScaledVector(this._panOffset,this.dampingFactor):this.target.add(this._panOffset),this.target.sub(this.cursor),this.target.clampLength(this.minTargetRadius,this.maxTargetRadius),this.target.add(this.cursor);let r=!1;if(this.zoomToCursor&&this._performCursorZoom||this.object.isOrthographicCamera)this._spherical.radius=this._clampDistance(this._spherical.radius);else{let a=this._spherical.radius;this._spherical.radius=this._clampDistance(this._spherical.radius*this._scale),r=a!=this._spherical.radius}if(nn.setFromSpherical(this._spherical),nn.applyQuaternion(this._quatInverse),e.copy(this.target).add(nn),this.object.lookAt(this.target),this.enableDamping===!0?(this._sphericalDelta.theta*=1-this.dampingFactor,this._sphericalDelta.phi*=1-this.dampingFactor,this._panOffset.multiplyScalar(1-this.dampingFactor)):(this._sphericalDelta.set(0,0,0),this._panOffset.set(0,0,0)),this.zoomToCursor&&this._performCursorZoom){let a=null;if(this.object.isPerspectiveCamera){let l=nn.length();a=this._clampDistance(l*this._scale);let o=l-a;this.object.position.addScaledVector(this._dollyDirection,o),this.object.updateMatrixWorld(),r=!!o}else if(this.object.isOrthographicCamera){let l=new F(this._mouse.x,this._mouse.y,0);l.unproject(this.object);let o=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),this.object.updateProjectionMatrix(),r=o!==this.object.zoom;let c=new F(this._mouse.x,this._mouse.y,0);c.unproject(this.object),this.object.position.sub(c).add(l),this.object.updateMatrixWorld(),a=nn.length()}else console.warn("WARNING: OrbitControls.js encountered an unknown camera type - zoom to cursor disabled."),this.zoomToCursor=!1;a!==null&&(this.screenSpacePanning?this.target.set(0,0,-1).transformDirection(this.object.matrix).multiplyScalar(a).add(this.object.position):(ec.origin.copy(this.object.position),ec.direction.set(0,0,-1).transformDirection(this.object.matrix),Math.abs(this.object.up.dot(ec.direction))<ny?this.object.lookAt(this.target):(_f.setFromNormalAndCoplanarPoint(this.object.up,this.target),ec.intersectPlane(_f,this.target))))}else if(this.object.isOrthographicCamera){let a=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),a!==this.object.zoom&&(this.object.updateProjectionMatrix(),r=!0)}return this._scale=1,this._performCursorZoom=!1,r||this._lastPosition.distanceToSquared(this.object.position)>Gh||8*(1-this._lastQuaternion.dot(this.object.quaternion))>Gh||this._lastTargetPosition.distanceToSquared(this.target)>Gh?(this.dispatchEvent(xf),this._lastPosition.copy(this.object.position),this._lastQuaternion.copy(this.object.quaternion),this._lastTargetPosition.copy(this.target),!0):!1}_getAutoRotationAngle(t){return t!==null?Un/60*this.autoRotateSpeed*t:Un/60/60*this.autoRotateSpeed}_getZoomScale(t){let e=Math.abs(t*.01);return Math.pow(.95,this.zoomSpeed*e)}_rotateLeft(t){this._sphericalDelta.theta-=t}_rotateUp(t){this._sphericalDelta.phi-=t}_panLeft(t,e){nn.setFromMatrixColumn(e,0),nn.multiplyScalar(-t),this._panOffset.add(nn)}_panUp(t,e){this.screenSpacePanning===!0?nn.setFromMatrixColumn(e,1):(nn.setFromMatrixColumn(e,0),nn.crossVectors(this.object.up,nn)),nn.multiplyScalar(t),this._panOffset.add(nn)}_pan(t,e){let n=this.domElement;if(this.object.isPerspectiveCamera){let s=this.object.position;nn.copy(s).sub(this.target);let r=nn.length();r*=Math.tan(this.object.fov/2*Math.PI/180),this._panLeft(2*t*r/n.clientHeight,this.object.matrix),this._panUp(2*e*r/n.clientHeight,this.object.matrix)}else this.object.isOrthographicCamera?(this._panLeft(t*(this.object.right-this.object.left)/this.object.zoom/n.clientWidth,this.object.matrix),this._panUp(e*(this.object.top-this.object.bottom)/this.object.zoom/n.clientHeight,this.object.matrix)):(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - pan disabled."),this.enablePan=!1)}_dollyOut(t){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale/=t:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_dollyIn(t){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale*=t:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_updateZoomParameters(t,e){if(!this.zoomToCursor)return;this._performCursorZoom=!0;let n=this.domElement.getBoundingClientRect(),s=t-n.left,r=e-n.top,a=n.width,l=n.height;this._mouse.x=s/a*2-1,this._mouse.y=-(r/l)*2+1,this._dollyDirection.set(this._mouse.x,this._mouse.y,1).unproject(this.object).sub(this.object.position).normalize()}_clampDistance(t){return Math.max(this.minDistance,Math.min(this.maxDistance,t))}_handleMouseDownRotate(t){this._rotateStart.set(t.clientX,t.clientY)}_handleMouseDownDolly(t){this._updateZoomParameters(t.clientX,t.clientX),this._dollyStart.set(t.clientX,t.clientY)}_handleMouseDownPan(t){this._panStart.set(t.clientX,t.clientY)}_handleMouseMoveRotate(t){this._rotateEnd.set(t.clientX,t.clientY),this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);let e=this.domElement;this._rotateLeft(Un*this._rotateDelta.x/e.clientHeight),this._rotateUp(Un*this._rotateDelta.y/e.clientHeight),this._rotateStart.copy(this._rotateEnd),this.update()}_handleMouseMoveDolly(t){this._dollyEnd.set(t.clientX,t.clientY),this._dollyDelta.subVectors(this._dollyEnd,this._dollyStart),this._dollyDelta.y>0?this._dollyOut(this._getZoomScale(this._dollyDelta.y)):this._dollyDelta.y<0&&this._dollyIn(this._getZoomScale(this._dollyDelta.y)),this._dollyStart.copy(this._dollyEnd),this.update()}_handleMouseMovePan(t){this._panEnd.set(t.clientX,t.clientY),this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd),this.update()}_handleMouseWheel(t){this._updateZoomParameters(t.clientX,t.clientY),t.deltaY<0?this._dollyIn(this._getZoomScale(t.deltaY)):t.deltaY>0&&this._dollyOut(this._getZoomScale(t.deltaY)),this.update()}_handleKeyDown(t){let e=!1;switch(t.code){case this.keys.UP:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateUp(Un*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,this.keyPanSpeed),e=!0;break;case this.keys.BOTTOM:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateUp(-Un*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,-this.keyPanSpeed),e=!0;break;case this.keys.LEFT:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateLeft(Un*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(this.keyPanSpeed,0),e=!0;break;case this.keys.RIGHT:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateLeft(-Un*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(-this.keyPanSpeed,0),e=!0;break}e&&(t.preventDefault(),this.update())}_handleTouchStartRotate(t){if(this._pointers.length===1)this._rotateStart.set(t.pageX,t.pageY);else{let e=this._getSecondPointerPosition(t),n=.5*(t.pageX+e.x),s=.5*(t.pageY+e.y);this._rotateStart.set(n,s)}}_handleTouchStartPan(t){if(this._pointers.length===1)this._panStart.set(t.pageX,t.pageY);else{let e=this._getSecondPointerPosition(t),n=.5*(t.pageX+e.x),s=.5*(t.pageY+e.y);this._panStart.set(n,s)}}_handleTouchStartDolly(t){let e=this._getSecondPointerPosition(t),n=t.pageX-e.x,s=t.pageY-e.y,r=Math.sqrt(n*n+s*s);this._dollyStart.set(0,r)}_handleTouchStartDollyPan(t){this.enableZoom&&this._handleTouchStartDolly(t),this.enablePan&&this._handleTouchStartPan(t)}_handleTouchStartDollyRotate(t){this.enableZoom&&this._handleTouchStartDolly(t),this.enableRotate&&this._handleTouchStartRotate(t)}_handleTouchMoveRotate(t){if(this._pointers.length==1)this._rotateEnd.set(t.pageX,t.pageY);else{let n=this._getSecondPointerPosition(t),s=.5*(t.pageX+n.x),r=.5*(t.pageY+n.y);this._rotateEnd.set(s,r)}this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);let e=this.domElement;this._rotateLeft(Un*this._rotateDelta.x/e.clientHeight),this._rotateUp(Un*this._rotateDelta.y/e.clientHeight),this._rotateStart.copy(this._rotateEnd)}_handleTouchMovePan(t){if(this._pointers.length===1)this._panEnd.set(t.pageX,t.pageY);else{let e=this._getSecondPointerPosition(t),n=.5*(t.pageX+e.x),s=.5*(t.pageY+e.y);this._panEnd.set(n,s)}this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd)}_handleTouchMoveDolly(t){let e=this._getSecondPointerPosition(t),n=t.pageX-e.x,s=t.pageY-e.y,r=Math.sqrt(n*n+s*s);this._dollyEnd.set(0,r),this._dollyDelta.set(0,Math.pow(this._dollyEnd.y/this._dollyStart.y,this.zoomSpeed)),this._dollyOut(this._dollyDelta.y),this._dollyStart.copy(this._dollyEnd);let a=(t.pageX+e.x)*.5,l=(t.pageY+e.y)*.5;this._updateZoomParameters(a,l)}_handleTouchMoveDollyPan(t){this.enableZoom&&this._handleTouchMoveDolly(t),this.enablePan&&this._handleTouchMovePan(t)}_handleTouchMoveDollyRotate(t){this.enableZoom&&this._handleTouchMoveDolly(t),this.enableRotate&&this._handleTouchMoveRotate(t)}_addPointer(t){this._pointers.push(t.pointerId)}_removePointer(t){delete this._pointerPositions[t.pointerId];for(let e=0;e<this._pointers.length;e++)if(this._pointers[e]==t.pointerId){this._pointers.splice(e,1);return}}_isTrackingPointer(t){for(let e=0;e<this._pointers.length;e++)if(this._pointers[e]==t.pointerId)return!0;return!1}_trackPointer(t){let e=this._pointerPositions[t.pointerId];e===void 0&&(e=new Xt,this._pointerPositions[t.pointerId]=e),e.set(t.pageX,t.pageY)}_getSecondPointerPosition(t){let e=t.pointerId===this._pointers[0]?this._pointers[1]:this._pointers[0];return this._pointerPositions[e]}_customWheelEvent(t){let e=t.deltaMode,n={clientX:t.clientX,clientY:t.clientY,deltaY:t.deltaY};switch(e){case 1:n.deltaY*=16;break;case 2:n.deltaY*=100;break}return t.ctrlKey&&!this._controlActive&&(n.deltaY*=10),n}};function iy(i){this.enabled!==!1&&(this._pointers.length===0&&(this.domElement.setPointerCapture(i.pointerId),this.domElement.ownerDocument.addEventListener("pointermove",this._onPointerMove),this.domElement.ownerDocument.addEventListener("pointerup",this._onPointerUp)),!this._isTrackingPointer(i)&&(this._addPointer(i),i.pointerType==="touch"?this._onTouchStart(i):this._onMouseDown(i),this._cursorStyle==="grab"&&(this.domElement.style.cursor="grabbing")))}function sy(i){this.enabled!==!1&&(i.pointerType==="touch"?this._onTouchMove(i):this._onMouseMove(i))}function ry(i){switch(this._removePointer(i),this._pointers.length){case 0:this.domElement.releasePointerCapture(i.pointerId),this.domElement.ownerDocument.removeEventListener("pointermove",this._onPointerMove),this.domElement.ownerDocument.removeEventListener("pointerup",this._onPointerUp),this.dispatchEvent(yf),this.state=Re.NONE,this._cursorStyle==="grab"&&(this.domElement.style.cursor="grab");break;case 1:let t=this._pointers[0],e=this._pointerPositions[t];this._onTouchStart({pointerId:t,pageX:e.x,pageY:e.y});break}}function ay(i){let t;switch(i.button){case 0:t=this.mouseButtons.LEFT;break;case 1:t=this.mouseButtons.MIDDLE;break;case 2:t=this.mouseButtons.RIGHT;break;default:t=-1}switch(t){case _s.DOLLY:if(this.enableZoom===!1)return;this._handleMouseDownDolly(i),this.state=Re.DOLLY;break;case _s.ROTATE:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=Re.PAN}else{if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=Re.ROTATE}break;case _s.PAN:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=Re.ROTATE}else{if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=Re.PAN}break;default:this.state=Re.NONE}this.state!==Re.NONE&&this.dispatchEvent(Wh)}function oy(i){switch(this.state){case Re.ROTATE:if(this.enableRotate===!1)return;this._handleMouseMoveRotate(i);break;case Re.DOLLY:if(this.enableZoom===!1)return;this._handleMouseMoveDolly(i);break;case Re.PAN:if(this.enablePan===!1)return;this._handleMouseMovePan(i);break}}function ly(i){this.enabled===!1||this.enableZoom===!1||this.state!==Re.NONE||(i.preventDefault(),this.dispatchEvent(Wh),this._handleMouseWheel(this._customWheelEvent(i)),this.dispatchEvent(yf))}function cy(i){this.enabled!==!1&&this._handleKeyDown(i)}function hy(i){switch(this._trackPointer(i),this._pointers.length){case 1:switch(this.touches.ONE){case ys.ROTATE:if(this.enableRotate===!1)return;this._handleTouchStartRotate(i),this.state=Re.TOUCH_ROTATE;break;case ys.PAN:if(this.enablePan===!1)return;this._handleTouchStartPan(i),this.state=Re.TOUCH_PAN;break;default:this.state=Re.NONE}break;case 2:switch(this.touches.TWO){case ys.DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchStartDollyPan(i),this.state=Re.TOUCH_DOLLY_PAN;break;case ys.DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchStartDollyRotate(i),this.state=Re.TOUCH_DOLLY_ROTATE;break;default:this.state=Re.NONE}break;default:this.state=Re.NONE}this.state!==Re.NONE&&this.dispatchEvent(Wh)}function uy(i){switch(this._trackPointer(i),this.state){case Re.TOUCH_ROTATE:if(this.enableRotate===!1)return;this._handleTouchMoveRotate(i),this.update();break;case Re.TOUCH_PAN:if(this.enablePan===!1)return;this._handleTouchMovePan(i),this.update();break;case Re.TOUCH_DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchMoveDollyPan(i),this.update();break;case Re.TOUCH_DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchMoveDollyRotate(i),this.update();break;default:this.state=Re.NONE}}function dy(i){this.enabled!==!1&&i.preventDefault()}function fy(i){i.key==="Control"&&(this._controlActive=!0,this.domElement.getRootNode().addEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}function py(i){i.key==="Control"&&(this._controlActive=!1,this.domElement.getRootNode().removeEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}var my=1.35,gy=8,Cn=.5,vf=.2;function Xa(i,t){return`#${new $t(i).offsetHSL(0,0,t).getHexString()}`}var Jr=class{constructor(t,e,n,s,r){ae(this,"root",new se);ae(this,"id");ae(this,"position");ae(this,"heading",0);ae(this,"path",[]);ae(this,"place",null);ae(this,"doing","rest");ae(this,"changedAt",0);ae(this,"settledAt",0);ae(this,"sit",0);ae(this,"stride",0);ae(this,"moving",!1);ae(this,"blinkAt");ae(this,"cheerUntil",0);ae(this,"body",new se);ae(this,"head",new se);ae(this,"eyes");ae(this,"legs");ae(this,"arms");ae(this,"book");ae(this,"cup");ae(this,"marker");ae(this,"paper");ae(this,"pages");ae(this,"geometries",[]);ae(this,"finishes");ae(this,"phase");this.id=t,this.finishes=r,this.position={...n},this.phase=t.length*1.7%(Math.PI*2),this.blinkAt=1+Math.random()*3;let a="#2a2a2e";this.legs=[-.085,.085].map(M=>{let m=this.limb(.24,.2,u=>u.add(I(.13,.25,.13,.035),e.pants,{y:-.12}),u=>{u.add(I(.12,.2,.12,.03),e.pants,{y:-.1}),u.add(I(.135,.065,.21,.03),a,{y:-.225,z:.035}),u.add(I(.13,.015,.2,.006),"#e8e4dc",{y:-.255,z:.035})});return m.upper.position.set(M,Cn,0),this.body.add(m.upper),m});let l=new ee;l.add(I(.36,.42,.22,.06),e.shirt,{y:Cn+.21}),l.add(I(.37,.05,.23,.02),Xa(e.pants,-.08),{y:Cn+.02}),l.add(I(.05,.035,.01),"#c9a24a",{y:Cn+.02,z:.116}),l.add(I(.2,.05,.16,.02),Xa(e.shirt,.08),{y:Cn+.41}),l.add(Ot(.055,.06,.06,10),e.skin,{y:Cn+.45}),e.accessory==="tie"?(l.add(I(.07,.04,.02),"#9e2b25",{y:Cn+.37,z:.115}),l.add(I(.06,.22,.02,.008),"#9e2b25",{y:Cn+.24,z:.115})):e.accessory==="scarf"?(l.add(gn(.15,.045,Math.PI*2,8,16),"#e8c547",{y:Cn+.43,rx:Math.PI/2}),l.add(I(.07,.16,.03,.012),"#e8c547",{y:Cn+.33,z:.12,x:.07})):e.accessory==="badge"&&(l.add(I(.08,.09,.02,.008),s,{y:Cn+.32,z:.115,x:-.09}),l.add(I(.05,.012,.022),"#ffffff",{y:Cn+.33,z:.116,x:-.09})),this.body.add(this.meshOf(l)),this.arms=[-.235,.235].map(M=>{let m=this.limb(.19,.16,u=>u.add(I(.1,.2,.1,.03),e.shirt,{y:-.095}),u=>{u.add(I(.092,.16,.092,.028),e.shirt,{y:-.08}),u.add(I(.096,.025,.096,.01),Xa(e.shirt,-.06),{y:-.15}),u.add(I(.095,.09,.095,.035),e.skin,{y:-.205})});return m.end.position.y=-.205,m.upper.position.set(M,Cn+.38,0),this.body.add(m.upper),m}),this.head.position.y=Cn+.42+.2;let o=new ee;o.add(I(.38,.36,.36,.08),e.skin);for(let M of[-1,1])o.add(I(.04,.08,.07,.02),e.skin,{x:M*.195,y:-.01});o.add(I(.05,.05,.04,.018),Xa(e.skin,-.06),{y:-.03,z:.18}),o.add(I(.09,.022,.02,.008),"#a5574b",{y:-.1,z:.175});for(let M of[-1,1])o.add(I(.055,.03,.01,.01),"#f08f8f",{x:M*.12,y:-.06,z:.181});this.addHair(o,e),this.addHeadwear(o,e),this.head.add(this.meshOf(o));let c=new ee;for(let M of[-1,1])c.add(I(.05,.07,.02,.012),"#1d1d22",{x:M*.08}),c.add(I(.016,.018,.005),"#ffffff",{x:M*.08+.01,y:.016,z:.011});this.eyes=this.meshOf(c,!1),this.eyes.position.set(0,.02,.18),this.head.add(this.eyes),this.body.add(this.head);let h=new ee;h.add(I(.22,.28,.05,.01),"#b5523b"),h.add(I(.2,.26,.052),"#f3efe7",{x:.012}),this.book=this.meshOf(h),this.book.position.set(0,.62,.24),this.book.visible=!1,this.body.add(this.book);let f=new ee;f.add(Ot(.038,.034,.09,12),"#ffffff"),f.add(gn(.024,.007,Math.PI*2,6,10),"#ffffff",{x:.04}),this.cup=this.meshOf(f),this.cup.position.set(0,-.06,.06),this.cup.visible=!1,this.arms[1].end.add(this.cup);let d=new ee;d.add(Ot(.014,.014,.15,8),s,{rx:Math.PI/2}),d.add(Ki(.014,.03,8),"#1d1d22",{z:.09,rx:Math.PI/2}),this.marker=this.meshOf(d),this.marker.position.set(0,-.05,.08),this.marker.visible=!1,this.arms[1].end.add(this.marker);let p=new ee;p.add(I(.21,.29,.006),"#fbfaf6");for(let M=0;M<6;M+=1)p.add(I(.15-M%3*.02,.012,.002),"#9aa1ab",{y:.1-M*.035,z:.004});this.paper=this.meshOf(p,!1),this.paper.position.set(0,.64,.25),this.paper.rotation.x=-.35,this.paper.visible=!1,this.body.add(this.paper);let x=new ee;for(let M=0;M<4;M+=1)x.add(I(.21,.007,.29),"#fbfaf6",{y:M*.008,ry:M%2*.05});this.pages=this.meshOf(x),this.pages.position.set(0,.6,.27),this.pages.visible=!1,this.body.add(this.pages),this.root.add(this.body),this.root.position.set(n.x,0,n.z),this.root.userData.personId=t,this.root.traverse(M=>{M.userData.personId=t})}meshOf(t,e=!0){let[n]=t.build(),s=n.geometry;this.geometries.push(s);let r=new kt(s,this.finishes.matte);return r.castShadow=e,r}limb(t,e,n,s){let r=new se,a=new ee;n(a),r.add(this.meshOf(a));let l=new se;l.position.y=-t;let o=new ee;s(o),l.add(this.meshOf(o));let c=new se;return c.position.y=-e,l.add(c),r.add(l),{upper:r,lower:l,end:c}}addHair(t,e){let n=e.hair;if(e.hairStyle==="bald"){for(let s of[-1,1])t.add(I(.03,.12,.26,.012),n,{x:s*.19,y:.02,z:-.04});return}t.add(I(.4,.11,.38,.05),n,{y:.17}),t.add(I(.4,.22,.07,.03),n,{y:.07,z:-.165});for(let s of[-1,1])t.add(I(.03,.12,.2,.012),n,{x:s*.195,y:.1,z:-.05});if(e.hairStyle==="short"&&t.add(I(.3,.06,.05,.02),n,{y:.15,z:.17,rx:.3}),e.hairStyle==="long"&&(t.add(I(.42,.44,.09,.03),n,{y:-.03,z:-.175}),t.add(I(.36,.06,.05,.02),n,{y:.15,z:.17,rx:.2})),e.hairStyle==="bun"&&t.add(Le(.09,12,10),n,{y:.27,z:-.12}),e.hairStyle==="spiky")for(let[s,r,a]of[[-.11,.06,-.3],[.02,-.06,0],[.12,.08,.3],[-.02,.14,.15],[.08,-.12,.2]])t.add(Ki(.065,.14,5),n,{x:s,y:.28,z:r,rz:a})}addHeadwear(t,e){let n="#1d1d22",s=e.accessory;if(s==="glasses"){for(let r of[-1,1])t.add(gn(.042,.009,Math.PI*2,6,16),n,{x:r*.08,y:.02,z:.19});t.add(I(.05,.012,.012),n,{y:.03,z:.19})}else if(s==="headset"){t.add(gn(.21,.018,Math.PI,6,16),n,{y:.06});for(let r of[-1,1])t.add(I(.05,.11,.11,.025),n,{x:r*.2});t.add(I(.02,.02,.15,.008),n,{x:.2,y:-.08,z:.08,ry:.4}),t.add(Le(.022,8,6),"#38c98f",{x:.17,y:-.09,z:.15})}else s==="cap"?(t.add(I(.41,.11,.39,.05),e.shirt,{y:.21}),t.add(I(.36,.025,.17,.01),e.shirt,{y:.17,z:.24}),t.add(Le(.025,8,6),Xa(e.shirt,.15),{y:.27})):s==="helmet"&&(t.add(Le(.245,16,10),"#f2c230",{y:.12,sy:.75}),t.add(I(.5,.025,.5,.01),"#f2c230",{y:.1}))}get action(){return this.doing}set action(t){t!==this.doing&&(this.doing=t,this.changedAt=performance.now()/1e3)}goTo(t,e){this.place=t,this.path=e}get walking(){return this.moving}get seated(){return this.sit>.5}cheer(t){this.cheerUntil=t+1.4}get top(){return Cn+.84+.12-this.sit*vf}update(t,e,n){let s=this.moving;if(this.moving=!1,this.path.length>0){let o=this.path[0],c=o.x-this.position.x,h=o.z-this.position.z,f=Math.hypot(c,h),d=n?f:my*t;f<=d||f<.01?(this.position.x=o.x,this.position.z=o.z,this.path.shift()):(this.position.x+=c/f*d,this.position.z+=h/f*d,this.turnToward(Math.atan2(c,h),t,n)),this.moving=this.path.length>0||f>d}s&&!this.moving&&(this.settledAt=e);let r=!this.moving&&this.place!==null;r&&this.place&&this.turnToward(Math.atan2(this.place.face.x-this.position.x,this.place.face.z-this.position.z),t,n);let a=r&&!!this.place?.sit&&!this.moving,l=n?1:1-Math.exp(-t*8);this.sit+=((a?1:0)-this.sit)*l,this.root.position.set(this.position.x,0,this.position.z),this.root.rotation.y=this.heading,this.pose(t,e,n)}turnToward(t,e,n){let s=t-this.heading;s=Math.atan2(Math.sin(s),Math.cos(s)),this.heading+=n?s:s*Math.min(1,e*gy)}pose(t,e,n){let[s,r]=this.legs,[a,l]=this.arms,o=e+this.phase;this.moving&&!n&&(this.stride+=t*9);let c=this.moving&&!n?Math.sin(this.stride):0,h=this.sit;s.upper.rotation.x=c*.55*(1-h)-Math.PI/2*h,r.upper.rotation.x=-c*.55*(1-h)-Math.PI/2*h,s.lower.rotation.x=Math.max(0,-c)*.6*(1-h)+Math.PI/2*h,r.lower.rotation.x=Math.max(0,c)*.6*(1-h)+Math.PI/2*h;let f=n||this.moving?0:Math.sin(o*1.6)*.004;this.body.position.y=-vf*h+(this.moving&&!n?Math.abs(Math.cos(this.stride))*.03:f),this.body.rotation.x=0;let d={x:-c*.5,z:-.06,elbow:-.15},p={x:c*.5,z:.06,elbow:-.15},x=0,M=0;this.book.visible=!1,this.cup.visible=!1,this.marker.visible=!1,this.paper.visible=!1,this.pages.visible=!1;let m=this.moving&&this.action!=="carry"?"walk":this.action,u=e-Math.max(this.settledAt,this.changedAt);if(e<this.cheerUntil&&!n){let v=Math.sin((this.cheerUntil-e)/1.4*Math.PI);d={x:0,z:-2.6,elbow:-.2},p={x:0,z:2.6,elbow:-.2},this.body.position.y+=v*.12}else if(m==="type"){let v=n?0:Math.sin(o*18)*.08;d={x:-1.05+v,z:.1,elbow:-.55},p={x:-1.05-v,z:-.1,elbow:-.55},x=.12+(n?0:Math.sin(o*2.1)*.03)}else if(m==="read"&&h<.5&&u<1.3&&!n){let v=Math.sin(Math.min(1,u/1.3)*Math.PI);p={x:-2.4*v,z:-.12,elbow:-.25},d={x:-.2,z:.08,elbow:-.3},x=-.18*v}else if(m==="read")d={x:-.95,z:.2,elbow:-.9},p={x:-.95,z:-.2,elbow:-.9},x=.3,this.book.visible=!0;else if(m==="browse"){let v=n?0:Math.max(0,Math.sin(o*.7))**8*.12;p={x:-1-v,z:-.2,elbow:-.55+v},d={x:-.8,z:.16,elbow:-.75},x=.1+(n?0:Math.sin(o*.45)*.04),M=n?0:Math.sin(o*.6)*.12}else if(m==="paper")d={x:-1,z:.16,elbow:-.85},p={x:-1,z:-.16,elbow:-.85},x=.26+(n?0:Math.sin(o*.5)*.04),this.paper.visible=!0;else if(m==="gaze")d={x:.45,z:.12,elbow:-.6},p={x:.45,z:-.12,elbow:-.6},x=-.1,M=n?0:Math.sin(o*.35)*.22;else if(m==="carry")d={x:-.75,z:.12,elbow:-.75},p={x:-.75,z:-.12,elbow:-.75},x=.12,this.pages.visible=!0;else if(m==="think")p={x:-1.6,z:-.35,elbow:-1.9},d={x:-.3,z:.25,elbow:-1.2},x=-.12,M=n?0:Math.sin(o*.9)*.15;else if(m==="write")p={x:-2.3+(n?0:Math.sin(o*3)*.15),z:-.2+(n?0:Math.cos(o*2.3)*.2),elbow:-.3},this.marker.visible=!0,M=n?0:Math.sin(o*1.1)*.12;else if(m==="talk")p={x:-.9+(n?0:Math.sin(o*2.6)*.25),z:-.15,elbow:-.9},d={x:-.4,z:.1,elbow:-.6},x=n?0:Math.sin(o*3.2)*.07,M=n?0:Math.sin(o*.7)*.25;else if(m==="raise")p={x:0,z:2.75+(n?0:Math.sin(o*6)*.18),elbow:-.25},x=-.1;else if(m==="slump")x=.45,d={x:.05,z:.04,elbow:0},p={x:.05,z:-.04,elbow:0};else if(m==="sip"){let v=n?0:Math.max(0,Math.sin(o*.8));p={x:-.5-v*1.2,z:-.15,elbow:-.6-v*1.4},this.cup.visible=!0}else if(m==="operate"){let v=n?0:Math.sin(o*12)*.1;d={x:-1.2+v,z:.12,elbow:-.4},p={x:-1.2-v,z:-.12,elbow:-.4},x=.05}else m==="rest"&&h>.5&&(d={x:-.5,z:.1,elbow:-.6},p={x:-.5,z:-.1,elbow:-.6});let A=n?1:1-Math.exp(-t*10);for(let[v,S]of[[a,d],[l,p]])v.upper.rotation.x+=(S.x-v.upper.rotation.x)*A,v.upper.rotation.z+=(S.z-v.upper.rotation.z)*A,v.lower.rotation.x+=(S.elbow-v.lower.rotation.x)*A;this.head.rotation.x+=(x-this.head.rotation.x)*A,this.head.rotation.y+=(M-this.head.rotation.y)*A,!n&&e>this.blinkAt&&(this.blinkAt=e+2.5+Math.random()*3.5),this.eyes.scale.y=!n&&e>this.blinkAt-.12?.15:1}dispose(){this.root.removeFromParent();for(let t of this.geometries)t.dispose()}};function Sf(i){return i&&/deepseek/i.test(i)?"whale":"small"}var Cs={x:(Ni.x0+Ni.x1)/2,z:(Ni.z0+Ni.z1)/2},Oi=Ni.x1-Ni.x0,yi=Ni.z1-Ni.z0,ts=.5,tr=.62,Ef=1.4,wf=ts+.04,sc=ts+tr-.04,bf={whale:sc-.165*Ef,small:ts+.28},Mf=6.5,xy=1.9,Xh=30,_y=2.3;function Tf(i,t){let e=t?"#4e3b2c":"#a5784f";i.within({x:Cs.x,z:Cs.z},()=>{i.add(I(Oi,ts,yi,.02),e,{y:ts/2},"satin");for(let r of[-1,0,1])i.add(I(Oi/3-.05,ts-.12,.01,.004),t?"#5f4836":"#bf9468",{x:r*Oi/3,y:ts/2,z:yi/2+.003},"satin",!1),i.add(I(.1,.012,.018,.005),"#c3c9d2",{x:r*Oi/3,y:ts-.1,z:yi/2+.014},"metal",!1);let n=ts,s={w:Oi-.06,d:yi-.06};i.add(I(Oi-.02,.024,yi-.02,.006),"#1d2027",{y:n+.012},"satin",!1);for(let r of[-1,1]){i.add(I(Oi-.02,.02,.02),"#1d2027",{y:n+tr-.01,z:r*(yi/2-.02)},"satin",!1),i.add(I(.02,.02,yi-.02),"#1d2027",{x:r*(Oi/2-.02),y:n+tr-.01},"satin",!1);for(let a of[-1,1])i.add(I(.018,tr,.018),"#1d2027",{x:r*(Oi/2-.02),y:n+tr/2,z:a*(yi/2-.02)},"satin",!1)}i.add(I(s.w-.1,.024,.06,.008),"#24272e",{y:n+tr+.012,z:-yi/2+.06},"satin",!1),i.add(I(s.w-.16,.006,.04),"#e6f8ff",{y:n+tr-.002,z:-yi/2+.06},"glow",!1),i.add(I(s.w,.04,s.d),t?"#b8a27a":"#d9c7a0",{y:n+.045},"matte",!1);for(let[r,a,l,o]of[[-.55,-.08,.1,"#7d7a74"],[-.44,.08,.065,"#8f8b83"],[.5,.1,.08,"#86827a"]])i.add(Le(l,10,8),o,{x:r,y:n+.075,z:a,sx:1.3,sy:.65},"matte",!1);for(let[r,a,l,o]of[[-.68,-.12,.34,.1],[-.62,.02,.26,-.15],[-.5,-.14,.2,.12],[.6,-.12,.36,-.08],[.66,.04,.28,.12],[.55,.14,.2,.2]])i.add(Kd(.012,l,8),t?"#3f7a52":"#4f9a63",{x:r,y:n+.065+l/2,z:a,rz:o},"matte",!1);for(let[r,a,l]of[[.62,.18,-.02],[.65,.28,-.03],[.63,.37,-.01]])i.add(Le(.01,8,6),"#e6fbff",{x:r,y:n+a,z:l},"glow",!1)})}var es={length:.48,radius:.11,tall:1.05,wide:.86,rise:.1},Af=i=>i<.35?es.radius*Math.sqrt(Math.max(0,1-(1-i/.35)**2.2)):es.radius*(1-.86*((i-.35)/.65)**1.6),Yh=i=>[es.length/2-i*es.length,i>.55?es.rise*((i-.55)/.45)**2:0];function ic(i,t,e){let[n,s]=Yh(i),r=Af(i);return new F(n,s+t*r*es.tall,e*Math.sqrt(Math.max(0,1-t*t))*r*es.wide)}var qh=ic(.22,1,0);function yy(i,t){if(i>.62)return!1;let e=.12-.82*i,n=e-(.07+.3*(1-i/.62)**.6);return t<=e&&t>=n}function vy(i,t){let s=[],r=[],a=new $t(i),l=new $t(t);for(let f=0;f<=72;f+=1){let d=f/72,[p,x]=Yh(d),M=Af(d);for(let m=0;m<=48;m+=1){let u=m/48*Math.PI*2,b=Math.cos(u);s.push(p,x+b*M*es.tall,Math.sin(u)*M*es.wide);let A=yy(d,b)?l:a;r.push(A.r,A.g,A.b)}}let o=[];for(let f=0;f<72;f+=1)for(let d=0;d<48;d+=1){let p=f*49+d,x=p+48+1;o.push(p,x,p+1,p+1,x,x+1)}let c=new je;c.setAttribute("position",new Ee(s,3)),c.setAttribute("color",new Ee(r,3)),c.setIndex(o),c.computeVertexNormals();let h=c.toNonIndexed();return c.dispose(),h}function nc(i){let t=new ee;i(t);let[e]=t.build();return e.geometry}function Rf(){let i="#4d6bfe",t="#f6f8ff",e=nc(h=>{for(let d of[-1,1]){let p=ic(.33,.14,d);h.add(Le(.017,16,12),t,{x:p.x,y:p.y,z:p.z,sz:.45}),h.add(Le(.0095,12,8),"#14171f",{x:p.x+.004,y:p.y+.001,z:p.z+d*.006,sz:.5});let x=ic(.42,-.55,d);h.add(Le(1,20,12),i,{x:x.x-.045,y:x.y-.025,z:x.z+d*.03,ry:d*.5,rz:.45,sx:.075,sy:.011,sz:.026})}let f=ic(.74,1,0);h.add(Le(1,14,10),i,{x:f.x,y:f.y+.008,rz:.6,sx:.032,sy:.022,sz:.007}),h.add(Le(1,10,8),"#26338a",{x:qh.x,y:qh.y,sx:.012,sy:.004,sz:.008})}),n=Wl([vy(i,t),e],!1);e.dispose();let[s,r]=Yh(1),a={body:n,tail:nc(h=>{h.add(Le(1,16,12),i,{sx:.028,sy:.02,sz:.02});for(let f of[-1,1])h.add(Le(1,24,14),i,{x:-.045,y:.014,z:f*.062,ry:f*.55,rz:.55,sx:.05,sy:.008,sz:.085})}),tailAt:[s,r]},l={body:nc(h=>{h.add(Le(1,16,12),"#ff8a3d",{sx:.05,sy:.034,sz:.022}),h.add(Le(1,12,10),"#fbfaf6",{x:.012,sx:.01,sy:.035,sz:.0235}),h.add(Le(1,10,8),"#ff7a2a",{y:.032,x:-.005,sx:.02,sy:.012,sz:.004});for(let f of[-1,1])h.add(Le(.006,8,6),"#14171f",{x:.033,y:.008,z:f*.016})}),tail:nc(h=>{h.add(Le(1,12,8),"#ff9a55",{x:-.02,sx:.024,sy:.026,sz:.004})}),tailAt:[-.045,0]},o=new ce(Oi-.05,sc-wf,yi-.05),c=new Vs(.018,10,8);return{whale:a,small:l,water:o,drop:c,dispose(){for(let h of[a,l])h.body.dispose(),h.tail.dispose();o.dispose(),c.dispose()}}}function Cf(i,t,e,n){let s=new Me({color:n?"#4a9fd0":"#8fd6f2",transparent:!0,opacity:.2,roughness:.05,metalness:0,depthWrite:!1}),r=new kt(i.water,s);r.position.set(Cs.x,(wf+sc)/2,Cs.z),r.renderOrder=1,e.add(r);let a=(m,u,b)=>{let A=new se;A.add(new kt(m.body,t.matte));let v=new se;return v.position.set(m.tailAt[0],m.tailAt[1],0),v.add(new kt(m.tail,t.matte)),A.add(v),A.scale.setScalar(b.scale??1),A.position.set(Cs.x,bf[u],Cs.z),e.add(A),{root:A,tail:v,...b,heading:0}},l={whale:[a(i.whale,"whale",{phase:0,speed:.18,reach:.36,depth:.02,bob:.008,scale:Ef})],small:[a(i.small,"small",{phase:.3,speed:.55,reach:.55,depth:.1,bob:.06}),a(i.small,"small",{phase:2.1,speed:.47,reach:.5,depth:.08,bob:.06,scale:.85}),a(i.small,"small",{phase:4,speed:.6,reach:.52,depth:.12,bob:.06,scale:.9})]},o=new be({color:"#e8f7ff",toneMapped:!1,transparent:!0,opacity:.9}),c=new hi(i.drop,o,Xh);c.frustumCulled=!1,c.visible=!1,e.add(c);let h=Array.from({length:Xh},(m,u)=>{let b=u%2===0?1:-1;return{delay:u/Xh*.6,up:1.3+u*37%7*.05,side:(u*53%11/11-.5)*.16,across:b*(.12+u*29%5*.025),size:.8+u*17%5*.12}}),f=new F,d=new ge,p=-1,x="small",M=m=>{x=m;for(let[u,b]of Object.entries(l))for(let A of b)A.root.visible=u===m;c.visible=!1};return M(x),{setFish(m){m!==x&&M(m)},tick(m,u,b){let A=x==="whale";for(let[R,g]of l[x].entries()){let w=b?g.phase:m*g.speed+g.phase,T=Math.sin(w)*g.reach,C=Math.cos(w)>=0?0:Math.PI;if(g.heading+=(C-g.heading)*(b?1:Math.min(1,u*2.5)),g.root.position.set(Cs.x+T,bf[x]+Math.sin(w*2.3+R)*g.bob,Cs.z+Math.sin(w*1.3+R*2)*g.depth),g.root.rotation.y=-g.heading,A){let D=b?0:Math.sin(m*2.2);g.tail.rotation.z=D*.14,g.root.rotation.z=D*.03}else g.tail.rotation.y=b?0:Math.sin(m*11+R)*.4}if(!A||b){c.visible=!1;return}let v=m%Mf;if(v>xy){c.visible=!1,p=-1;return}let S=l.whale[0].root,E=Math.floor(m/Mf);p!==E&&(p=E,f.copy(qh).multiplyScalar(S.scale.x).applyAxisAngle(on.DEFAULT_UP,S.rotation.y).add(S.position)),c.visible=!0;for(let[R,g]of h.entries()){let w=v-g.delay,T=f.y+g.up*w-_y/2*w*w,C=w>0&&T>sc?g.size:0;d.makeScale(C,C,C),d.setPosition(f.x+g.side*w,T,f.z+g.across*w),c.setMatrixAt(R,d)}c.instanceMatrix.needsUpdate=!0},dispose(){s.dispose(),o.dispose(),c.dispose()}}}var si=.18,by=I(.58,.34,.008),My=gn(.42,.025,Math.PI*2,8,40);function Sy(i){let t=document.createElement("canvas");t.width=512,t.height=512;let e=t.getContext("2d");e.fillStyle=i?"#76604b":"#c9a37c",e.fillRect(0,0,512,512);for(let s=0;s<8;s+=1){let r=s%2*128;for(let a=-1;a<3;a+=1){let l=(s*7+a*3)%5/5;e.fillStyle=i?`rgba(0,0,0,${.08+l*.08})`:`rgba(90,55,25,${.05+l*.07})`,e.fillRect(a*256+r+2,s*64+2,252,60),e.fillStyle=i?"rgba(255,255,255,0.03)":"rgba(255,255,255,0.12)",e.fillRect(a*256+r+10,s*64+20+l*20,236,2)}}let n=new qi(t);return n.wrapS=Si,n.wrapT=Si,n.repeat.set(3,2.2),n.colorSpace=Ge,n.anisotropy=4,n}function Ey(i){return i?{wall:"#4d5466",wallLow:"#434a5b",trim:"#262a33",skirt:"#2b2f38",sky:"#1d2e5c",frame:"#2c303a",deskTop:"#6b5a4a",deskFrame:"#3a3f4b",chair:"#2f3442",seat:"#3d4456",wood:"#4e3b2c",woodLight:"#5f4836",sofa:"#5a4b72",cushion:"#6d5d88",rug:"#3c3346",rugLounge:"#2f3a4a",pot:"#8a5a44",soil:"#3a2a20",leaf:"#4f8a5b",leafLight:"#6aa86f",counter:"#4e3b2c",top:"#6b5a4a",cooler:"#b9bfc8",lampShade:"#ffd9a0"}:{wall:"#f1ece4",wallLow:"#e6ddd0",trim:"#d9cfc1",skirt:"#e9e4dc",sky:"#bfe3ff",frame:"#e8e2d8",deskTop:"#e8dccb",deskFrame:"#9aa1ab",chair:"#4c5566",seat:"#5c677c",wood:"#a5784f",woodLight:"#bf9468",sofa:"#7f9cc0",cushion:"#9bb4d4",rug:"#d9cbe0",rugLounge:"#c9d6e3",pot:"#c1785a",soil:"#5a4030",leaf:"#4f8a5b",leafLight:"#6aa86f",counter:"#a5784f",top:"#e8dccb",cooler:"#d9dde3",lampShade:"#fff1d6"}}function wy(i){let t=new ee,e=Ey(i.dark),n=Ct.x1-Ct.x0,s=Ct.z1-Ct.z0;t.add(I(n+.1,.12,s+.1),e.skirt,{y:-.3},"matte",!1),t.add(I(n+.12,.05,.05),e.trim,{y:-.21,z:Ct.z1+.06},"satin",!1),t.add(I(.05,.05,s+.12),e.trim,{x:Ct.x1+.06,y:-.21},"satin",!1);let r=.95;t.add(I(n,r,si+.02),e.wallLow,{y:r/2,z:Ct.z0-si/2}),t.add(I(n,Ct.height-r,si),e.wall,{y:r+(Ct.height-r)/2,z:Ct.z0-si/2}),t.add(I(si+.02,r,s+si),e.wallLow,{x:Ct.x0-si/2,y:r/2,z:-si/2}),t.add(I(si,Ct.height-r,s+si),e.wall,{x:Ct.x0-si/2,y:r+(Ct.height-r)/2,z:-si/2});for(let[N,G]of[[.06,.12],[r,.04],[Ct.height-.02,.05]])t.add(I(n,G,.04),e.trim,{y:N,z:Ct.z0+.02},"satin",!1),t.add(I(.04,G,s),e.trim,{x:Ct.x0+.02,y:N},"satin",!1);t.add(I(4.7,1.36,.06,.02),e.frame,{y:1.62,z:Ct.z0+.03},"satin",!1);for(let N of[-1.65,-.55,.55,1.65])t.add(I(1.04,1.14,.02),e.sky,{x:N,y:1.62,z:Ct.z0+.065},"glow",!1);for(let N of[-1.1,0,1.1])t.add(I(.06,1.16,.05),e.frame,{x:N,y:1.62,z:Ct.z0+.08},"satin",!1);if(t.add(I(4.6,.04,.05),e.frame,{y:1.62,z:Ct.z0+.08},"satin",!1),t.add(I(4.9,.05,.16,.015),e.trim,{y:.92,z:Ct.z0+.08},"satin",!1),i.dark){for(let[N,G]of[[-1.8,1.95],[-.6,1.8],[.5,2],[1.6,1.75],[-1.3,1.45],[.9,1.4],[1.9,2.05],[-.2,2.1]])t.add(I(.03,.03,.01),"#ffffff",{x:N,y:G,z:Ct.z0+.08},"glow",!1);t.add(Ot(.13,.13,.01,20),"#fff1c4",{x:1.55,y:1.95,z:Ct.z0+.08,rx:Math.PI/2},"glow",!1)}else for(let[N,G,X]of[[-1.5,1.95,1],[.9,1.75,.8]])for(let[K,nt,tt]of[[0,0,.12],[.13,.02,.09],[-.12,-.01,.08]])t.add(Le(tt*X,10,6),"#ffffff",{x:N+K*X,y:G+nt*X,z:Ct.z0+.075,sz:.2},"glow",!1);t.add(I(1,.76,.05,.015),e.woodLight,{x:-4.05,y:1.62,z:Ct.z0+.03},"satin",!1),t.add(I(.88,.64,.02),"#f3efe7",{x:-4.05,y:1.62,z:Ct.z0+.06},"matte",!1);for(let[N,G,X,K,nt]of[[-4.25,1.7,.3,.36,"#e07a5f"],[-3.9,1.52,.4,.22,"#3d405b"],[-3.8,1.78,.18,.18,"#f2cc8f"]])t.add(I(X,K,.01),nt,{x:N,y:G,z:Ct.z0+.075},"matte",!1);t.add(Ot(.27,.27,.04,32),"#fbfaf7",{x:3.6,y:1.85,z:Ct.z0+.04,rx:Math.PI/2},"satin",!1),t.add(gn(.27,.025,Math.PI*2,6,32),"#3b3b40",{x:3.6,y:1.85,z:Ct.z0+.06},"metal",!1);for(let N=0;N<12;N+=1){let G=N/12*Math.PI*2;t.add(I(.018,N%3===0?.05:.03,.01),"#3b3b40",{x:3.6+Math.sin(G)*.21,y:1.85+Math.cos(G)*.21,z:Ct.z0+.065,rz:-G},"matte",!1)}for(let N=0;N<Dh;N+=1){let{x:G,z:X}=Xr(N),K=Qi.width+(N===0?.2:0);t.add(I(K,.045,Qi.depth,.015),e.deskTop,{x:G,y:.645,z:X},"satin");for(let tt of[-1,1])t.add(I(.04,.62,Qi.depth-.06,.01),e.deskFrame,{x:G+tt*(K/2-.05),y:.31,z:X},"metal");t.add(I(K-.14,.28,.02),e.deskFrame,{x:G,y:.46,z:X+Qi.depth/2-.06},"metal"),t.add(I(.22,.014,.14,.006),"#2a2d35",{x:G,y:.674,z:X+.2},"metal"),t.add(I(.04,.2,.03),"#5d6470",{x:G,y:.77,z:X+.22},"metal"),t.add(I(.64,.4,.035,.014),"#1d2027",{x:G,y:1,z:X+.2},"satin"),t.add(I(.38,.018,.13,.006),"#2a2d35",{x:G,y:.676,z:X-.12},"satin"),t.add(I(.34,.006,.1),"#3d414b",{x:G,y:.687,z:X-.12},"matte",!1),t.add(I(.06,.024,.09,.011),"#2a2d35",{x:G+.29,y:.68,z:X-.12},"satin",!1);let nt=N%3;N===0?(t.add(Ot(.07,.08,.02,16),"#2a2d35",{x:G-.55,y:.678,z:X+.15},"metal"),t.add(I(.02,.36,.02),"#5d6470",{x:G-.55,y:.85,z:X+.1,rx:-.35},"metal"),t.add(Ki(.09,.12,16),e.lampShade,{x:G-.55,y:1.02,z:X-.02,rx:Math.PI*.85},i.dark?"glow":"satin",!1)):nt===0?(t.add(Ot(.045,.04,.1,14),"#fbfaf7",{x:G-.38,y:.72,z:X-.05},"satin",!1),t.add(gn(.03,.008,Math.PI*2,6,12),"#fbfaf7",{x:G-.33,y:.72,z:X-.05},"satin",!1)):nt===1?(t.add(Ot(.06,.05,.09,12),e.pot,{x:G-.4,y:.71,z:X+.05},"matte",!1),t.add(jn(.08),e.leafLight,{x:G-.4,y:.81,z:X+.05},"matte",!1)):(t.add(I(.22,.02,.28,.005),["#3d6fa5","#c06c84","#e0a13a"][N%3],{x:G-.36,y:.678,z:X-.05,ry:.2},"matte",!1),t.add(Ot(.008,.008,.16,6),"#1d2027",{x:G-.3,y:.692,z:X-.06,rz:Math.PI/2,ry:.5},"satin",!1)),t.add(I(.46,.07,.44,.03),e.seat,{x:G,y:.29,z:Di},"matte"),t.add(I(.44,.46,.06,.03),e.chair,{x:G,y:.62,z:Di-.23,rx:-.08},"matte"),t.add(I(.05,.2,.03),"#3a3f4b",{x:G,y:.4,z:Di-.22},"metal");for(let tt of[-1,1])t.add(I(.04,.12,.04),"#3a3f4b",{x:G+tt*.24,y:.37,z:Di-.02},"metal"),t.add(I(.06,.025,.24,.01),e.chair,{x:G+tt*.24,y:.44,z:Di-.02},"matte");t.add(Ot(.025,.025,.2,10),"#5d6470",{x:G,y:.16,z:Di},"metal");for(let tt=0;tt<5;tt+=1){let lt=tt/5*Math.PI*2;t.add(I(.04,.025,.24),"#3a3f4b",{x:G+Math.sin(lt)*.12,y:.05,z:Di+Math.cos(lt)*.12,ry:lt},"metal",!1),t.add(Le(.025,8,6),"#1d2027",{x:G+Math.sin(lt)*.24,y:.025,z:Di+Math.cos(lt)*.24},"satin",!1)}}let a=2,l=(hn.x0+hn.x1)/2,o=(hn.z0+hn.z1)/2,c=hn.x1-hn.x0,h=hn.z1-hn.z0;for(let N of[hn.z0,hn.z1])t.add(I(c,a,.05,.01),e.wood,{x:l,y:a/2,z:N},"satin");t.add(I(.03,a,h),e.woodLight,{x:hn.x0+.02,y:a/2,z:o},"matte",!1);let f=["#b5523b","#3d6fa5","#e0a13a","#4f8a5b","#7b5ea7","#c06c84","#2f4858","#d9c5a0"];for(let N=0;N<5;N+=1){let G=.04+N*.48;if(t.add(I(c,.035,h,.008),e.wood,{x:l,y:G,z:o},"satin"),N===4)break;let X=hn.z0+.08,K=N*3;for(;X<hn.z1-.14;){let nt=.06+K*37%5*.012,tt=.26+K*13%4*.035,lt=K%9===4?.22:0;t.add(I(.22,tt,nt,.006),f[K%f.length],{x:hn.x0+.17,y:G+.02+tt/2,z:X+nt/2+lt*.3,rx:lt},"matte",!1),X+=nt+.01+lt*.4,K+=1}}t.add(Ot(.06,.08,.2,14),"#e8e2d8",{x:l,y:a+.12,z:hn.z0+.35},"satin",!1),t.add(jn(.09),e.leaf,{x:l,y:a+.27,z:hn.z0+.35},"matte",!1);let d=(ti.z0+ti.z1)/2,p=ti.z1-ti.z0;t.add(I(.04,1.08,p+.08,.012),"#aeb5bf",{x:ti.x,y:1.45,z:d},"metal"),t.add(I(.02,1,p),"#fcfcfa",{x:ti.x+.025,y:1.45,z:d},"satin",!1),t.add(I(.08,.025,p,.008),"#aeb5bf",{x:ti.x+.06,y:.93,z:d},"metal",!1);for(let[N,G]of[[-.3,"#d1495b"],[-.18,"#3f88c5"],[.1,"#2a9d8f"]])t.add(Ot(.012,.012,.12,8),G,{x:ti.x+.07,y:.955,z:d+N,rx:Math.PI/2},"satin",!1);t.add(Ot(1.32,1.32,.015,48),e.rug,{x:we.x,y:.008,z:we.z},"matte",!1),t.add(gn(1.25,.02,Math.PI*2,4,48),i.dark?"#4a4057":"#c9b8d3",{x:we.x,y:.016,z:we.z,rx:Math.PI/2},"matte",!1),t.add(Ot(we.radius,we.radius,.05,40),e.deskTop,{x:we.x,y:.61,z:we.z},"satin"),t.add(Ot(we.radius-.02,we.radius-.08,.04,40),e.deskFrame,{x:we.x,y:.57,z:we.z},"metal",!1),t.add(Ot(.06,.06,.52,14),"#5d6470",{x:we.x,y:.31,z:we.z},"metal"),t.add(Ot(.32,.36,.04,28),"#3a3f4b",{x:we.x,y:.03,z:we.z},"metal");for(let N of qr)t.add(Ot(.2,.2,.07,20),e.seat,{x:N.x,y:.29,z:N.z},"matte"),t.add(Ot(.025,.025,.24,8),"#5d6470",{x:N.x,y:.14,z:N.z},"metal",!1),t.add(Ot(.15,.17,.025,18),"#3a3f4b",{x:N.x,y:.013,z:N.z},"metal",!1);let x=(un.x0+un.x1)/2,M=(un.z0+un.z1)/2;t.add(I(un.x1-un.x0,2,un.z1-un.z0,.02),"#23262e",{x,y:1,z:M},"satin"),t.add(I(.02,1.86,un.z1-un.z0-.08),"#30343e",{x:un.x0-.002,y:1,z:M},"satin",!1);for(let N=0;N<7;N+=1)t.add(I(.012,.012,un.z1-un.z0-.16),"#16181d",{x:un.x0-.012,y:.3+N*.22,z:M},"matte",!1);let m=(dn.x0+dn.x1)/2,u=(dn.z0+dn.z1)/2;t.add(I(dn.x1-dn.x0,.05,dn.z1-dn.z0,.012),"#5d6470",{x:m,y:.9,z:u},"metal"),t.add(I(.06,.88,.06),"#3a3f4b",{x:m,y:.44,z:u},"metal"),t.add(I(.4,.03,.5,.01),"#3a3f4b",{x:m,y:.015,z:u},"metal",!1);for(let N of[-2.75,-2.05]){t.add(I(.04,.42,.62,.012),"#1d2027",{x:dn.x1-.12,y:1.2,z:N},"satin"),t.add(I(.01,.34,.54),i.dark?"#1f6f5a":"#2f8f74",{x:dn.x1-.145,y:1.2,z:N},"glow",!1);for(let G=0;G<4;G+=1)t.add(I(.004,.02,.18+G%2*.14),"#8af0c8",{x:dn.x1-.152,y:1.3-G*.07,z:N-.12+G%2*.07},"glow",!1)}let b=($e.x0+$e.x1)/2,A=($e.z0+$e.z1)/2,v=$e.z1-$e.z0;t.add(I(1.9,.012,2.5,.004),e.rugLounge,{x:-4.6,y:.007,z:A},"matte",!1),t.add(I($e.x1-$e.x0,.2,v,.05),e.sofa,{x:b,y:.14,z:A}),t.add(I(.2,.55,v,.06),e.sofa,{x:$e.x0+.1,y:.42,z:A});for(let N of[$e.z0+.08,$e.z1-.08])t.add(I($e.x1-$e.x0,.36,.16,.06),e.sofa,{x:b,y:.3,z:N});for(let N of[A-v/4+.04,A+v/4-.04])t.add(I($e.x1-$e.x0-.24,.09,v/2-.14,.04),e.cushion,{x:b+.1,y:.29,z:N}),t.add(I(.14,.34,v/2-.16,.05),e.cushion,{x:$e.x0+.26,y:.52,z:N,rz:-.18});t.add(I(.1,.22,.22,.05),i.accent,{x:$e.x0+.36,y:.45,z:$e.z1-.32,rz:-.25,ry:.3},"matte"),t.add(Ot(.14,.16,.025,18),"#2a2d35",{x:-5.62,y:.013,z:4.28},"metal",!1),t.add(Ot(.015,.015,1.5,8),"#5d6470",{x:-5.62,y:.76,z:4.28},"metal"),t.add(Ot(.14,.2,.26,20),e.lampShade,{x:-5.62,y:1.58,z:4.28},i.dark?"glow":"satin",!1);let S=(Nn.x0+Nn.x1)/2,E=(Nn.z0+Nn.z1)/2,R=Nn.x1-Nn.x0;t.add(I(R,.84,Nn.z1-Nn.z0,.02),e.counter,{x:S,y:.42,z:E});for(let N of[-R/4,R/4])t.add(I(R/2-.06,.72,.01),e.woodLight,{x:S+N,y:.44,z:Nn.z0-.003},"satin",!1),t.add(I(.1,.015,.02),"#aeb5bf",{x:S+N,y:.7,z:Nn.z0-.015},"metal",!1);t.add(I(R+.06,.04,Nn.z1-Nn.z0+.06,.012),e.top,{x:S,y:.86,z:E},"satin"),t.add(I(.3,.36,.26,.03),"#2b2e36",{x:S-.25,y:1.06,z:E},"metal"),t.add(I(.22,.02,.12,.006),"#5d6470",{x:S-.25,y:.89,z:E-.08},"metal",!1),t.add(I(.04,.04,.01),"#ff6b4a",{x:S-.25,y:1.16,z:E-.135},"glow",!1);for(let N of[.18,.32])t.add(Ot(.045,.04,.1,14),"#fbfaf7",{x:S+N,y:.93,z:E},"satin",!1);t.add(I(.36,.8,.36,.04),e.cooler,{x:Xn.x,y:.4,z:Xn.z},"satin"),t.add(I(.08,.05,.05),"#3f88c5",{x:Xn.x-.19,y:.62,z:Xn.z},"satin",!1),t.add(Ot(.15,.15,.4,20),"#8fc9ff",{x:Xn.x,y:1,z:Xn.z},"glass",!1),t.add(Ot(.05,.05,.05,12),"#3f88c5",{x:Xn.x,y:1.22,z:Xn.z},"satin",!1);let g=(We.z0+We.z1)/2;for(let N of[We.z0,We.z1])t.add(I(.14,2.2,.1,.02),e.woodLight,{x:We.x+.04,y:1.1,z:N},"satin");t.add(I(.16,.14,We.z1-We.z0+.1,.02),e.woodLight,{x:We.x+.04,y:2.2,z:g},"satin"),t.add(I(.55,.012,.95,.004),e.rugLounge,{x:We.x-.4,y:.007,z:g},"matte",!1);let w=2.2,T=i.dark?"#7fb6d6":"#cfe8f4",C=i.dark?"#8a93a3":"#aeb5bf",D=he.z-Ct.z0;t.add(I(.025,w,D),T,{x:he.x,y:w/2,z:Ct.z0+D/2},"glass",!1);for(let[N,G]of[[he.x,he.door.x0],[he.door.x1,dn.x0]])t.add(I(G-N,w,.025),T,{x:(N+G)/2,y:w/2,z:he.z},"glass",!1);for(let N of[.02,w])t.add(I(.05,.04,D),C,{x:he.x,y:N,z:Ct.z0+D/2},"metal",!1),t.add(I(dn.x0-he.x,.04,.05),C,{x:(he.x+dn.x0)/2,y:N,z:he.z},"metal",!1);for(let N of[Ct.z0+.7,Ct.z0+1.4,he.z])t.add(I(.05,w,.05),C,{x:he.x,y:w/2,z:N},"metal",!1);for(let N of[he.door.x0,he.door.x1])t.add(I(.04,w,.05),C,{x:N,y:w/2,z:he.z},"metal",!1);let V=(vn.x0+vn.x1)/2,U=(vn.z0+vn.z1)/2,z=vn.x1-vn.x0,q=vn.z1-vn.z0;t.add(I(z,.55,q,.02),e.wood,{x:V,y:.275,z:U},"satin"),t.add(I(z-.08,.004,.01),e.woodLight,{x:V,y:.3,z:vn.z1+.002},"matte",!1),t.add(I(z-.1,.24,q-.06,.03),i.dark?"#c9ccd2":"#eef0f3",{x:V,y:.67,z:U-.02},"satin"),t.add(I(z-.16,.04,q-.14,.012),"#3a3f4b",{x:V,y:.81,z:U-.04},"satin",!1),t.add(I(.3,.012,.16,.004),"#5d6470",{x:V,y:.6,z:vn.z1+.04,rx:.12},"satin",!1),t.add(I(.03,.03,.01),"#38d39f",{x:V+.22,y:.74,z:vn.z1-.03},"glow",!1),Tf(t,i.dark);for(let[N,G]of Nh.entries()){t.add(Ot(.21,.15,.38,18),e.pot,{x:G.x,y:.19,z:G.z},"satin"),t.add(gn(.205,.02,Math.PI*2,6,18),e.pot,{x:G.x,y:.38,z:G.z,rx:Math.PI/2},"satin",!1),t.add(Ot(.19,.19,.02,16),e.soil,{x:G.x,y:.36,z:G.z},"matte",!1);let X=N%2===1;X&&t.add(Ot(.02,.025,.7,6),"#5b4636",{x:G.x,y:.7,z:G.z},"matte");let K=X?1.05:.58,nt=[[0,0,0,.3,e.leaf],[.14,.12,.05,.2,e.leafLight],[-.12,.16,-.06,.18,e.leafLight],[.02,.3,.02,.17,e.leaf],[-.05,.06,.15,.16,e.leafLight]];for(let[tt,lt,zt,Lt,gt]of nt)t.add(jn(Lt*(X?.9:1)),gt,{x:G.x+tt,y:K+lt,z:G.z+zt,ry:tt*7},"matte")}return t}function Pf(i,t){let e=wy(i).build(),n=Sy(i.dark),s=Ct.x1-Ct.x0,r=Ct.z1-Ct.z0,a=new ce(s,.24,r);a.translate(0,-.12,0);let l=new Me({map:n,roughness:.82}),o=["#38d39f","#4aa3ff","#f2c230"],c=[new ee,new ee];for(let g=0;g<7;g+=1)for(let w=0;w<3;w+=1)c[(g+w)%2].add(I(.012,.035,.06),o[w],{x:un.x0-.016,y:.36+g*.22,z:un.z0+.2+w*.25},"glow",!1);let h=c.map(g=>g.build()[0].geometry),f=I(.03,.14,.01).clone().translate(0,.06,0),d=I(.02,.21,.01).clone().translate(0,.095,0),p=new Me({color:"#25252a",roughness:.5}),x=new ee;for(let g=0;g<3;g+=1)x.add(I(.21,.006,.28),"#fbfaf6",{y:g*.007,ry:(g-1)*.07});let M=x.build()[0].geometry,m=he.door.x1-he.door.x0,u=new ee;u.add(I(m-.04,2.1,.02),i.dark?"#7fb6d6":"#cfe8f4",{y:1.07},"glass",!1);for(let g of[-m/2+.02,m/2-.02])u.add(I(.035,2.12,.035),i.dark?"#8a93a3":"#aeb5bf",{x:g,y:1.07},"metal",!1);u.add(I(.02,.32,.04,.008),"#5d6470",{x:m/2-.09,y:1.05,z:.03},"metal",!1);let b=u.build(),A=new ce(dn.x0-he.x,.025,.03),v=We.z1-We.z0-.12,S=new ee;S.add(I(.05,2.06,v,.015),i.dark?"#5f4836":"#bf9468",{y:1.04,z:v/2},"satin"),S.add(I(.06,.6,v-.3,.01),i.dark?"#4e3b2c":"#a5784f",{y:1.5,z:v/2},"satin",!1),S.add(I(.1,.03,.12,.01),"#aeb5bf",{y:1,z:v-.12},"metal",!1);let E=S.build(),R=Rf();return{theme:i,finishes:t,furniture:e,floor:{geometry:a,material:l,texture:n},leds:h,hands:{hour:f,minute:d,material:p},printout:M,sandbox:{door:b,strip:A},entrance:E,aquarium:R,dispose(){R.dispose();for(let g of e)g.geometry.dispose();for(let g of E)g.geometry.dispose();for(let g of b)g.geometry.dispose();A.dispose(),a.dispose(),l.dispose(),n.dispose();for(let g of h)g.dispose();f.dispose(),d.dispose(),p.dispose(),M.dispose()}}}function If(i){let{theme:t,finishes:e}=i,n=new se;for(let E of Ii(i.furniture,e))n.add(E);let s=new kt(i.floor.geometry,i.floor.material);s.receiveShadow=!0,s.matrixAutoUpdate=!1,n.add(s);let r=[],a=[];for(let E=0;E<Dh;E+=1){let{x:R,z:g}=Xr(E),w=new Me({color:"#0e1420",emissive:"#203048",emissiveIntensity:.35,roughness:.3});a.push(w),r.push(w);let T=new kt(by,w);T.position.set(R,1,g+.18),n.add(T)}let l=new se;l.position.set(ti.x+.04,1.45,(ti.z0+ti.z1)/2),n.add(l);let o=new Me({color:t.accent,emissive:t.accent,emissiveIntensity:1.4,transparent:!0,opacity:.85});r.push(o);let c=new kt(My,o);c.position.set(we.x,.95,we.z),c.rotation.x=Math.PI/2,c.visible=!1,n.add(c);let h=i.leds.map(E=>{let R=new be({vertexColors:!0,toneMapped:!1});return r.push(R),n.add(new kt(E,R)),R}),f=new kt(i.hands.hour,i.hands.material),d=new kt(i.hands.minute,i.hands.material);f.position.set(3.6,1.85,Ct.z0+.08),d.position.set(3.6,1.85,Ct.z0+.09),n.add(f,d);let p=Xr(0),x=new Ti("#ffc978",0,3.2,1.6);x.position.set(p.x-.5,.98,p.z-.05),x.visible=!1,n.add(x);let M=new kt(i.printout,e.matte);M.position.set((vn.x0+vn.x1)/2,.615,vn.z1+.05),M.rotation.x=.12,M.visible=!1,n.add(M);let m=new se;for(let E of Ii(i.sandbox.door,e))m.add(E);m.position.set((he.door.x0+he.door.x1)/2,0,he.z+.045),n.add(m);let u=new be({color:t.dark?"#3a4558":"#c4ccd6",toneMapped:!1});r.push(u);let b=new kt(i.sandbox.strip,u);b.position.set((he.x+dn.x0)/2,2.25,he.z),n.add(b);let A=new se;for(let E of Ii(i.entrance,e))A.add(E);A.position.set(We.x+.04,0,We.z0+.06),n.add(A);let v=[];if(t.dark)for(let[E,R,g]of[[0,2.1,-1.8],[-5.3,1.6,4],[1.6,2,1.5]]){let w=new Ti("#ffcf8a",9,9,1.4);w.position.set(E,R,g),n.add(w),v.push(w)}let S=Cf(i.aquarium,e,n,t.dark);return{group:n,screens:a,notes:l,ring:c,leds:h,clock:{hour:f,minute:d},lamps:v,deskLamp:x,printout:M,sandbox:{door:m,strip:u},entrance:A,aquarium:S,dispose(){n.removeFromParent(),S.dispose();for(let E of l.children)E.material.dispose();for(let E of r)E.dispose();for(let E of v)E.dispose();x.dispose()}}}function jh(i,t,e){let n=[...i.querySelectorAll(".studio-tag, .studio-floor-sign")];for(let s=n.length-1;s>=0;s--){let r=n[s],a=r.getBoundingClientRect();if(!a.width||t<a.left||t>a.right||e<a.top||e>a.bottom)continue;let l=getComputedStyle(r);if(l.visibility!=="hidden"&&Number(l.opacity)>=.1)return r}return null}var er=new F(-.3,.5,.2),rc={polar:.98,azimuth:.62},qa={polar:1.16,azimuth:.72},ac=7.1,Bi=Ct.height+.4,jr=1.2,Zh=-.87,Ty=1.75,oc=16,Ay=7,lc=1.35,Lf=1e3/30,zf=20,$h={x:Yr.x,z:Yr.z},Kh={x:We.x,z:(We.z0+We.z1)/2},Ry=1.5,Cy=1.35,Jh=new F(-5,11,8),Py=I(.01,.2,.22,.004),Df={x:(he.door.x0+he.door.x1)/2,z:he.z},Iy=14,Ly=1.6,zy=1e3/12,Dy=4e3,Ny=.75,Uy=1e3/30,Fy=1e3,cc={polar:1.02,azimuth:.5},Qr=class{constructor(t){ae(this,"from");ae(this,"to");ae(this,"start",0);ae(this,"seconds",0);this.from=t,this.to=t}get target(){return this.to}set(t,e,n){t!==this.to&&(this.from=this.value(e),this.to=t,this.start=e,this.seconds=n)}value(t){return this.seconds<=0?this.to:this.from+(this.to-this.from)*Nf(Math.min(1,(t-this.start)/this.seconds))}done(t){return this.seconds<=0||t-this.start>=this.seconds}};function Nf(i){return i<.5?4*i*i*i:1-(-2*i+2)**3/2}function Ps(i){return`${i.x.toFixed(2)},${i.z.toFixed(2)}`}function Oy(i,t){let{actor:e}=i;return i.errand?i.errand.phase==="carry"?"carry":"operate":e.state==="waiting"?"raise":e.state==="failed"?"slump":e.state==="answering"?"type":e.state==="working"?e.spot==="shelf"?"read":e.spot==="terminal"||e.spot==="sandbox"?"operate":e.spot==="board"?"write":e.spot==="table"?"talk":e.spot==="window"?"gaze":e.activity==="search"?"browse":e.activity==="read"?"paper":e.activity==="thinking"?"think":"type":Kl.includes(t)?"gaze":t===Va[0]||t.x===Va[1].x&&t.z===Va[1].z?"sip":"rest"}function Uf(i,t,e,n,s="room"){let r=s,a=()=>e.pixelRatio??(r==="backdrop"?Ny:Math.min(window.devicePixelRatio||1,1.25)),l=Math.min(Math.max(e.speed??1,.25),4),o=new Vr({antialias:!0,alpha:!0,powerPreference:"low-power",failIfMajorPerformanceCaveat:e.requireGpu===!0});o.setPixelRatio(a()),o.shadowMap.enabled=!0,o.shadowMap.type=Zi,o.shadowMap.autoUpdate=!1,o.outputColorSpace=Ge,o.toneMapping=qs,o.toneMappingExposure=e.dark?1.05:1,o.domElement.classList.add("studio-canvas"),o.domElement.setAttribute("aria-hidden","true"),i.prepend(o.domElement);let c=new Bs,h=new Je(30,1,.5,160),f=new Kr(h,o.domElement);f.target.copy(er),f.enableDamping=!0,f.dampingFactor=.08,f.enablePan=!1,f.rotateSpeed=.6,f.zoomSpeed=.8,f.enabled=r==="room",i.dataset.mode=r,c.add(new Gs(e.dark?"#9fb0e0":"#fff6ea",e.dark?"#3a3040":"#b8a48c",e.dark?1.35:1.5));let d=new Yi(e.dark?"#b9c8ff":"#fff1dc",e.dark?1.5:2.2);d.castShadow=!0,d.shadow.mapSize.set(1024,1024),d.shadow.camera.near=1,d.shadow.bias=-6e-4,d.shadow.radius=3,c.add(d,d.target);let p=new Yi(e.dark?"#5b4b8a":"#cfe3ff",e.dark?.35:.6);p.position.set(9,5,-3),c.add(p);let x=ql(),M=Pf({dark:e.dark,accent:e.accent},x),m="small",u=e.dark?"#3b4252":"#d8d2c8",b=Ct.x1-Ct.x0,A=Ct.z1-Ct.z0,v=new ee;for(let[Z,j]of[[Ct.x1+.13,Ct.z1+.13],[Ct.x1+.13,Ct.z0-.05],[Ct.x0-.05,Ct.z1+.13]])v.add(I(.26,Ct.height,.26,.03),u,{x:Z,y:Ct.height/2,z:j},"satin"),v.add(I(.3,.06,.3,.01),e.dark?"#4a5263":"#e6e0d6",{x:Z,y:Ct.height-.03,z:j},"satin",!1);let S=v.build(),E=new ee;E.add(I(b+.5,.36,A+.5),e.dark?"#2b2f38":"#e9e4dc",{y:-.18},"matte",!1),E.add(I(b+.3,.02,A+.3),e.dark?"#353a45":"#d9d3c8",{y:.01},"matte",!1);for(let[Z,j,dt,bt]of[[b+.5,.14,0,Ct.z0-.18],[b+.5,.14,0,Ct.z1+.18],[.14,A+.5,Ct.x0-.18,0],[.14,A+.5,Ct.x1+.18,0]])E.add(I(Z,.42,j,.02),u,{x:dt,y:.21,z:bt},"satin");E.add(I(1.6,.6,1.1,.04),e.dark?"#4d5466":"#c9c3b8",{x:-3.2,y:.3,z:-2.6},"satin");for(let Z of[-.45,0,.45])E.add(Ot(.17,.17,.04,16),"#2a2d35",{x:-3.2+Z,y:.62,z:-2.6},"metal",!1);for(let Z=0;Z<2;Z+=1)for(let j=0;j<3;j+=1){let dt=.4+j*1.25,bt=.6+Z*1.15;E.add(I(1.1,.04,.9,.01),e.dark?"#1c2a4a":"#2c4a7a",{x:dt,y:.42,z:bt,rx:-.3},"satin"),E.add(I(.04,.32,.04),"#8a919c",{x:dt,y:.18,z:bt-.3},"metal",!1)}E.add(Ot(.04,.05,1.6,8),u,{x:4.2,y:.8,z:-3.4},"metal"),E.add(Le(.09,10,8),"#ff3b30",{x:4.2,y:1.65,z:-3.4},"glow",!1);let R=new se;for(let Z of Ii(E.build(),x))R.add(Z);let g=new Qr(0),w=!1,T=new ee;T.add(I(b+2*jr,.5,A+2*jr,.04),e.dark?"#262a33":"#cfc8bc",{y:Zh+.25},"matte",!1),T.add(I(b+2.2,.03,A+2.2),e.dark?"#2f4a3a":"#9cc49a",{y:-.36},"matte",!1),T.add(I(1.6,.035,1.1),e.dark?"#3a3f4b":"#e6e0d6",{x:4.4,y:-.355,z:Ct.z1+.7},"matte",!1);for(let[Z,j]of[[-6.6,5.2],[6.6,5.2],[-6.6,-5],[6.7,-1]])T.add(jn(.4),"#4f8a5b",{x:Z,y:-.1,z:j},"matte"),T.add(jn(.26),"#6aa86f",{x:Z+.2,y:.1,z:j-.1},"matte");let C=new se;for(let Z of Ii(T.build(),x))C.add(Z);c.add(R,C);let D=document.createElement("canvas");D.width=D.height=128;let V=D.getContext("2d");if(V){let Z=V.createRadialGradient(64,64,0,64,64,64);Z.addColorStop(0,e.dark?"rgba(0, 0, 0, 0.55)":"rgba(38, 48, 78, 0.28)"),Z.addColorStop(.5,e.dark?"rgba(0, 0, 0, 0.25)":"rgba(38, 48, 78, 0.12)"),Z.addColorStop(1,"rgba(0, 0, 0, 0)"),V.fillStyle=Z,V.fillRect(0,0,128,128)}let U=new qi(D);U.colorSpace=Ge;let z=new kt(new Hs(b+9,A+9),new be({map:U,transparent:!0,depthWrite:!1,toneMapped:!1}));z.rotation.x=-Math.PI/2,z.position.y=-.26,z.renderOrder=-1,c.add(z);let q=new ei(cf()),N=new Map,G=[],X=e.reducedMotion,K=!1,nt=!1,tt=null,lt=null,zt="",Lt="",gt="",J=!1,et=null,pt=()=>G.length>=2,At=()=>tt===null?void 0:N.get(tt),Mt=()=>pt()&&tt===null,qt=Z=>{let j=ln.degToRad(h.fov)/2,dt=Math.atan(Math.tan(j)*h.aspect);return Z/Math.sin(Math.min(j,dt))},ve=(Z,j,dt,bt,_)=>{let P=new F().setFromSpherical(new zn(1,j,dt)),H=new F(0,1,0).cross(P).normalize(),O=P.clone().cross(H),k=Math.tan(ln.degToRad(h.fov)/2),st=k*h.aspect,ct=new F,_t=0;for(let yt=0;yt<8;yt+=1){ct.set(yt&1?_.x:bt.x,yt&2?_.y:bt.y,yt&4?_.z:bt.z).sub(Z);let Nt=ct.dot(P);_t=Math.max(_t,Nt+Math.abs(ct.dot(H))/st,Nt+Math.abs(ct.dot(O))/k)}return _t},Jt=()=>G.length*Bi+.6,te=()=>{let Z=G[0],j=Z?.members.get("lead"),dt=j?.person.position??Ha(0),bt=j!==void 0&&j.actor.state!=="idle"&&j.actor.state!=="done"&&j.actor.state!=="stopped",_=new F(Math.cos(cc.azimuth),0,-Math.sin(cc.azimuth)),P=h.aspect<1,H=Z!==void 0&&[...Z.members.values()].some(ct=>!ct.actor.lead&&(ct.actor.state==="working"||ct.actor.state==="arriving"||ct.actor.state==="waiting")),O=(ct,_t)=>{if(!P)return ct;let yt=ct.radius*Math.tan(ln.degToRad(h.fov)/2);return{...ct,target:ct.target.clone().setY(ct.target.y-2*_t*yt/Math.sin(ct.polar))}};if(H)return O({target:er.clone().addScaledVector(_,P?0:-.9),radius:qt(ac)*.52,...cc},.08);let k=e.centered===!0,st=er.clone().lerp(new F(dt.x,.75,dt.z),k?1:P?.85:.7).addScaledVector(_,k||P?0:-1.1);return O({target:st,radius:qt(ac)*(bt?.31:.38)*(k&&P?.85:1),...cc},k?.06:.18)},ne=()=>{if(r==="backdrop")return te();if(Mt()){let dt=Jt(),bt=new F(Math.cos(qa.azimuth),0,-Math.sin(qa.azimuth)).multiplyScalar(ac*.3),_=new F(er.x,dt/2-.5,er.z).add(bt),P=new F(Ct.x0-jr,Zh,Ct.z0-jr),H=new F(Ct.x1+jr,G.length*Bi+Ty,Ct.z1+jr);return{target:_,radius:ve(_,qa.polar,qa.azimuth,P,H)*1.04,...qa}}let Z=At()?.index??0,j=er.clone().setY(er.y+Z*Bi);if(h.aspect<1){let dt=Z*Bi,bt=new F(Ct.x0,dt,Ct.z0),_=new F(Ct.x1,dt+Ct.height,Ct.z1);return{target:j,radius:ve(j,rc.polar,rc.azimuth,bt,_)*1.02,...rc}}return{target:j,radius:qt(ac),...rc}},jt=()=>{let Z=new zn().setFromVector3(h.position.clone().sub(f.target));return{target:f.target.clone(),radius:Z.radius,polar:Z.phi,azimuth:Z.theta}},xe=Z=>{f.target.copy(Z.target),h.position.setFromSpherical(new zn(Z.radius,Z.polar,Z.azimuth)).add(Z.target),h.lookAt(Z.target)},ze=()=>{let Z=ne();f.minDistance=Z.radius*.45,f.maxDistance=Z.radius*1.5,f.minPolarAngle=.35,f.maxPolarAngle=Mt()?1.45:1.28,f.minAzimuthAngle=-.4,f.maxAzimuthAngle=1.5},Ie=Z=>{let j=ne();if(!Z||X||!J){lt=null,f.enabled=r==="room",xe(j),ze(),f.update();return}lt={from:jt(),to:j,start:performance.now()/1e3},f.enabled=!1},pe=Z=>{if(!lt)return;let j=Nf(Math.min(1,(Z-lt.start)/lc)),{from:dt,to:bt}=lt,_=Math.sin(j*Math.PI)*(Mt()?.04:.08);xe({target:dt.target.clone().lerp(bt.target,j),radius:ln.lerp(dt.radius,bt.radius,j)*(1+_),polar:ln.lerp(dt.polar,bt.polar,j),azimuth:ln.lerp(dt.azimuth,bt.azimuth,j)}),Z-lt.start>=lc&&(lt=null,f.enabled=r==="room",xe(bt),ze(),f.update())},_e=(Z,j=!1)=>{let dt=X||j?0:lc,bt=At();for(let H of G){let O=pt()&&bt!==void 0&&H.index>bt.index;H.y.set(H.index*Bi+(O?oc:0),Z,dt)}let _=G.length*Bi;pt()?w||(w=!0,g=new Qr(_+oc)):w=!1,g.set(_+(pt()&&bt!==void 0?oc:0),Z,dt);let P=Mt()?`building|${G.length}`:`floor|${bt?.index??0}`;P!==Lt&&(Lt=P,Ie(!j))},Y=Z=>{let{actor:j,tag:dt,bubble:bt}=Z;dt.dataset.state=j.state,dt.dataset.lead=j.lead?"true":"false",dt.querySelector(".studio-tag-name").textContent=j.name,dt.querySelector(".studio-tag-state").textContent=j.stateLabel,dt.setAttribute("aria-label",`${j.name}: ${j.stateLabel}`),Z.tagSize=null,bt.textContent=j.bubble??"",bt.hidden=!j.bubble,bt.dataset.state=j.state},Xe=Z=>{let{view:j}=Z;Z.sign.dataset.busy=j.busy?"true":"false",Z.sign.querySelector(".studio-floor-number").textContent=j.number,Z.sign.querySelector(".studio-floor-title").textContent=j.title,Z.sign.querySelector(".studio-floor-summary").textContent=j.summary,Z.sign.setAttribute("aria-label",`${j.number} ${j.title}: ${j.summary}`),Z.signWidth=Z.sign.offsetWidth},ye=(Z,j,dt,bt)=>{let _=Ha(dt),P=!!j.leaves&&j.state!=="working"&&j.state!=="arriving"&&j.state!=="waiting"&&j.state!=="answering",H=new Jr(j.id,j.look,Z.first&&!P?_:$h,e.accent,x);Z.first&&!P&&(H.heading=Math.atan2(_.face.x-_.x,_.face.z-_.z)),H.root.visible=!P,Z.group.add(H.root);let O=document.createElement("button");O.type="button",O.className="studio-tag",O.tabIndex=-1;let k=document.createElement("span");k.className="studio-tag-dot";let st=document.createElement("span");st.className="studio-tag-name";let ct=document.createElement("span");ct.className="studio-tag-state",O.append(k,st,ct),O.addEventListener("click",()=>n.pick(Z.id,j.id));let _t=document.createElement("div");_t.className="studio-bubble",t.append(_t,O);let yt={person:H,actor:j,desk:dt,tag:O,bubble:_t,since:bt,idleNext:bt+4+Math.random()*6,idlePlace:null,spotSince:bt,errands:new Set(j.errand?[j.errand]:[]),errand:null,gone:P,enters:0,key:P?Ps(Yr):"",tagSize:null};return Y(yt),yt},L=Z=>{Z.person.dispose(),Z.tag.remove(),Z.bubble.remove()},y=(Z,j)=>{let dt=new se;dt.userData.floorId=Z.id;let bt=If(M);bt.aquarium.setFish(m),dt.add(bt.group);let _=new se;for(let O of Ii(S,x))_.add(O);dt.add(_);let P=document.createElement("button");P.type="button",P.className="studio-floor-sign",P.tabIndex=-1;for(let O of["studio-floor-number","studio-floor-title","studio-floor-summary"]){let k=document.createElement("span");k.className=O,P.append(k)}P.addEventListener("click",()=>n.pickFloor(Z.id)),P.style.visibility="hidden",t.append(P);let H={id:Z.id,index:j,view:Z,group:dt,room:bt,posts:_,members:new Map,first:!0,notesSignature:"",y:new Qr(j*Bi),sign:P,signWidth:0};return dt.position.y=j*Bi,c.add(dt),H},$=Z=>{for(let j of Z.members.values())L(j);Z.members.clear(),Z.room.dispose(),Z.group.removeFromParent(),Z.sign.remove()},Q=(Z,j,dt)=>{let bt=new Set(j.map(H=>H.id));for(let[H,O]of Z.members)bt.has(H)||(L(O),Z.members.delete(H));let _=1,P=0;for(let H of j){let O=H.lead?0:_++,k=Z.members.get(H.id);if(!k){let st=ye(Z,H,O,dt);!Z.first&&!st.gone&&(st.enters=dt+Ry*P++),Z.members.set(H.id,st);continue}k.actor.state!==H.state&&(k.since=dt,H.state==="done"&&k.person.cheer(dt)),k.actor.spot!==H.spot&&(k.spotSince=dt),k.actor=H,k.desk=O,Y(k)}Z.first=!1},it=Z=>{let j=performance.now()/1e3,dt=N.size===0,bt=new Set(Z.map(k=>k.id));for(let[k,st]of N)bt.has(k)||($(st),N.delete(k));let _=[],P=[];Z.forEach((k,st)=>{let ct=N.get(k.id);ct||(ct=y(k,st),N.set(k.id,ct),P.push(ct)),ct.index=st,ct.view=k,Xe(ct),Q(ct,k.cast,j),_.push(ct)});let H=pt();G=_,pt()?(!H||tt!==null&&!N.has(tt))&&(tt=null):tt=G[0]?.id??null;let O=At();for(let k of P){let st=pt()&&O!==void 0&&k.index>O.index,ct=k.index*Bi+(st?oc:0);k.y=new Qr(ct+(Mt()&&!dt&&!X?Ay:0)),k.y.set(ct,j,lc),k.group.position.y=k.y.value(j)}_e(j,dt)},xt=(Z,j)=>{let dt=new Map,bt=(_,P)=>{for(let H of _){let O=Ps(H);if(!dt.has(O))return dt.set(O,1),H}return P};for(let _ of Z.members.values()){let{actor:P,person:H}=_,O=Ha(_.desk),k=P.state==="idle"||P.state==="stopped"||P.state==="done"&&j-_.since>zf;P.errand&&!_.errands.has(P.errand)&&(_.errands.add(P.errand),X||(_.errand={phase:"fetch",at:null})),_.errand&&(k||P.state==="waiting"||P.state==="failed")&&(_.errand=null);let st=!!P.leaves&&(k||P.state==="failed"&&j-_.since>zf);!st&&_.gone&&(_.gone=!1,H.root.visible=!0);let ct;if(st)ct=Yr,_.key===Ps(Yr)&&!H.walking&&!_.gone&&(_.gone=!0,H.root.visible=!1);else if(_.errand){let yt=_.errand,Nt=Yt=>_.key===Ps(Yt)&&!H.walking;yt.phase==="fetch"&&Nt(Uh)?(yt.at??(yt.at=j),j-yt.at>Ly&&(yt.phase="carry")):yt.phase==="carry"&&Nt(O)&&(_.errand=null),ct=_.errand?.phase==="fetch"?Uh:O}else if(k){if(!X&&r==="room"&&j>_.idleNext&&!H.walking){let yt=[O,...Va].filter(Nt=>Nt===O||!dt.has(Ps(Nt)));_.idlePlace=yt[Math.floor(Math.random()*yt.length)]??O,_.idleNext=j+(P.lead?22:12)+Math.random()*16}ct=_.idlePlace??O}else _.idlePlace=null,_.idleNext=j+6,ct=P.spot==="shelf"?bt(sf,O):P.spot==="terminal"?bt(af,O):P.spot==="sandbox"?bt(of,O):P.spot==="door"?bt([lf],O):P.spot==="table"?bt(P.lead?[qr[3],...qr]:qr,O):P.spot==="board"?bt([rf],O):P.spot==="window"?Kl[j-_.spotSince>Iy&&!X?Math.floor((j-_.spotSince)/7)%2:0]:O;j<_.enters&&(ct={x:$h.x,z:$h.z,face:Kh,sit:!1}),dt.set(Ps(ct),1);let _t=Ps(ct);_t!==_.key&&(_.key=_t,H.goTo(ct,q.path(H.position,ct))),H.action=Oy(_,ct)}},wt=(Z,j)=>{let{room:dt,members:bt}=Z,_=new Map;for(let ft of bt.values())ft.person.seated&&ft.key===Ps(Ha(ft.desk))&&_.set(ft.desk,ft);dt.screens.forEach((ft,Be)=>{let oe=_.get(Be),fn=oe?.person.action,Fn=fn==="type"||fn==="think"||fn==="browse",On=fn==="browse";ft.emissive.set(On?e.dark?"#8ab4ea":"#9cc3f2":Fn?e.dark?"#3d7bd9":"#4b8fe6":"#203048"),ft.emissiveIntensity=Fn?(On?1:.9)+(X?0:Math.sin(j*(On?3:7)+Be)*(On?.14:.08)):oe?.45:.25});let P=[...bt.values()].filter(ft=>!ft.actor.lead&&(ft.actor.state==="working"||ft.actor.state==="arriving")),H=P.map(ft=>ft.actor.look.shirt).join();if(H!==Z.notesSignature){Z.notesSignature=H;for(let ft of[...dt.notes.children])dt.notes.remove(ft),ft.material.dispose();P.forEach((ft,Be)=>{let oe=new kt(Py,new Me({color:ft.actor.look.shirt,roughness:.9}));oe.position.set(0,.22-Math.floor(Be/2)*.28,-.45+Be%2*.32),oe.rotation.x=(Be%2?-1:1)*.06,dt.notes.add(oe)})}let O=bt.get("lead"),ct=[...bt.values()].every(ft=>ft.actor.lead)&&O!==void 0&&(O.actor.state==="working"||O.actor.state==="answering"||O.actor.state==="waiting"||O.errand!==null)?e.dark?6:2.5:0;dt.deskLamp.intensity+=(ct-dt.deskLamp.intensity)*(X?1:.08),dt.printout.visible=[...bt.values()].some(ft=>ft.errand?.phase==="fetch");let _t=[...bt.values()].some(ft=>Math.hypot(ft.person.position.x-Df.x,ft.person.position.z-Df.z)<1),yt=dt.sandbox.door,Yt=(he.door.x0+he.door.x1)/2-(_t?(he.door.x1-he.door.x0)*.9:0);yt.position.x+=(Yt-yt.position.x)*(X?1:.12);let ie=[...bt.values()].some(ft=>ft.actor.spot==="sandbox"&&ft.person.action==="operate"&&!ft.person.walking),Ut=[...bt.values()].some(ft=>ft.actor.spot==="door"&&ft.actor.state==="waiting"),ue=X?1:.75+Math.sin(j*3)*.25;dt.sandbox.strip.color.set(ie?"#38d39f":Ut?"#f2b33d":e.dark?"#3a4558":"#c4ccd6"),(ie||Ut)&&dt.sandbox.strip.color.multiplyScalar(ue*1.4);let Oe=[...bt.values()].some(ft=>!ft.gone&&Math.hypot(ft.person.position.x-Kh.x,ft.person.position.z-Kh.z)<1.3);dt.entrance.rotation.y+=((Oe?Cy:0)-dt.entrance.rotation.y)*(X?1:.14);let Te=[...bt.values()].some(ft=>ft.actor.state==="working"&&ft.actor.spot==="table");dt.ring.visible=Te,Te&&!X&&(dt.ring.rotation.z=j*.8,dt.ring.position.y=.95+Math.sin(j*2)*.03);let Se=[...bt.values()].some(ft=>ft.person.action==="operate"&&!ft.person.walking);dt.leds.forEach((ft,Be)=>{ft.color.setScalar(Se&&!X?Math.sin(j*9+Be*Math.PI)>0?1.6:.25:.7)});let Ve=new Date;dt.clock.minute.rotation.z=-((Ve.getMinutes()+Ve.getSeconds()/60)/60)*Math.PI*2,dt.clock.hour.rotation.z=-((Ve.getHours()%12+Ve.getMinutes()/60)/12)*Math.PI*2},rt=Z=>{let j=lt===null&&g.done(Z);for(let st of G)st.group.position.y=st.y.value(Z),j&&(j=st.y.done(Z));R.position.y=g.value(Z);let dt=At(),bt=pt()&&(dt===void 0||!j);R.visible=bt,C.visible=bt,z.position.y=bt?Zh-.01:(dt?.group.position.y??0)-.26;for(let st of G){let ct=!pt()||st===dt;st.group.visible=bt||ct,st.posts.visible=bt,st.room.lamps.forEach((_t,yt)=>{_t.visible=ct&&j||bt&&yt===0}),st.room.deskLamp.visible=ct&&j}let _=bt?Jt():Ct.height,P=bt?_/2-.5:(dt?.index??0)*Bi+1,H=bt?Math.max(9,(15+.66*_)/2+1):9,O=`${P.toFixed(2)}|${H.toFixed(2)}`;if(O!==zt){zt=O,d.target.position.set(0,P,0),d.position.copy(Jh).multiplyScalar(1+H/Jh.length()).add(d.target.position);let st=d.shadow.camera;st.left=-H,st.right=H,st.top=H,st.bottom=-H,st.far=2*(Jh.length()+H)+10,st.updateProjectionMatrix()}let k=`${dt===void 0&&pt()?"building":"floor"}|${j}`;return k!==gt&&(gt=k,t.dataset.view=dt===void 0&&pt()?"building":"floor",t.dataset.moving=j?"false":"true"),j},ot=new F,St=(Z,j,dt)=>(ot.set(Z,j,dt).project(h),{x:(ot.x*.5+.5)*i.clientWidth,y:(-ot.y*.5+.5)*i.clientHeight,z:ot.z,visible:ot.z<1&&Math.abs(ot.x)<1.2&&Math.abs(ot.y)<1.2}),Bt=Z=>{let j=jt(),dt=te(),bt=X?1:1-Math.exp(-Z*1.4);return j.target.distanceTo(dt.target)+Math.abs(j.radius-dt.radius)*.2+Math.abs(j.polar-dt.polar)+Math.abs(j.azimuth-dt.azimuth)<.01?!1:(xe({target:j.target.lerp(dt.target,bt),radius:ln.lerp(j.radius,dt.radius,bt),polar:ln.lerp(j.polar,dt.polar,bt),azimuth:ln.lerp(j.azimuth,dt.azimuth,bt)}),!0)},Pt=()=>{let Z=At(),j=Mt()&&lt===null;for(let dt of G){let bt=dt.group.position.y,_=(!pt()||dt===Z)&&lt===null,P=[...dt.members.values()].map(st=>({member:st,point:St(st.person.position.x,bt+st.person.top+.12,st.person.position.z)})).sort((st,ct)=>st.point.z-ct.point.z),H=[];for(let{member:st,point:ct}of P){let _t=_&&ct.visible&&!st.gone,yt=!1;if(_t){let Yt=st.tagSize;Yt||(st.tag.dataset.compact="false",Yt=[st.tag.offsetWidth,st.tag.offsetHeight],Yt[0]>0&&(st.tagSize=Yt));let[ie,Ut]=Yt,ue=[ct.x-ie/2,ct.y-Ut,ct.x+ie/2,ct.y];yt=H.some(([Oe,Te,Se,Ve])=>ue[0]<Se+2&&ue[2]>Oe-2&&ue[1]<Ve+2&&ue[3]>Te-2),yt||H.push(ue)}st.tag.dataset.compact!==String(yt)&&(st.tag.dataset.compact=String(yt)),st.tag.style.transform=`translate(${ct.x.toFixed(1)}px, ${ct.y.toFixed(1)}px) translate(-50%, -100%)`,st.bubble.style.transform=`translate(${ct.x.toFixed(1)}px, ${(ct.y-30).toFixed(1)}px) translate(-50%, -100%)`,st.tag.style.visibility=_t?"visible":"hidden",st.bubble.style.visibility=_t?"visible":"hidden";let Nt=String(Math.round((1-ct.z)*1e4));st.tag.style.zIndex=Nt,st.bubble.style.zIndex=Nt}let O=St(Ct.x1+.4,bt+Ct.height*.5,Ct.z0+.6),k=Math.max(8,Math.min(O.x+12,i.clientWidth-dt.signWidth-8));dt.sign.style.transform=`translate(${k.toFixed(1)}px, ${O.y.toFixed(1)}px) translate(0, -50%)`,dt.sign.style.visibility=j&&O.visible?"visible":"hidden",dt.sign.dataset.hover=et===dt.id?"true":"false"}},Et=()=>{o.setPixelRatio(a());let Z=Math.max(1,i.clientWidth),j=Math.max(1,i.clientHeight);o.setSize(Z,j,!1),h.aspect=Z/j,h.updateProjectionMatrix(),!J&&i.clientWidth>0&&(J=!0,Ie(!1))},Ht=new ResizeObserver(()=>{Et(),Sn()});Ht.observe(i),Et();let Vt=new Ws,Wt=new Xt,W=null,Rt=Z=>{for(let j=Z;j;j=j.parent)if(typeof j.userData.floorId=="string")return j.userData.floorId;return null},ht=Z=>{if(lt)return null;let j=o.domElement.getBoundingClientRect();if(Wt.set((Z.clientX-j.left)/j.width*2-1,-((Z.clientY-j.top)/j.height)*2+1),Vt.setFromCamera(Wt,h),Mt()){let P=Vt.intersectObjects(G.map(O=>O.group),!0)[0],H=P?Rt(P.object):null;return H?{floor:H,person:null}:null}let dt=At()??G[0];if(!dt)return null;let bt=Vt.intersectObjects([...dt.members.values()].filter(P=>!P.gone).map(P=>P.person.root),!0)[0],_=bt?bt.object.userData.personId??null:null;return _?{floor:dt.id,person:_}:null},Tt=0,It=()=>{Tt=performance.now()+1500,Sn()},B=Z=>{W={x:Z.clientX,y:Z.clientY},It()},at=Z=>{if(W&&Math.hypot(Z.clientX-W.x,Z.clientY-W.y)<5){let j=jh(t,Z.clientX,Z.clientY),dt=j?null:ht(Z);j?j.click():dt?.person?n.pick(dt.floor,dt.person):dt&&n.pickFloor(dt.floor)}W=null},ut=Z=>{if(Z.buttons){It();return}let j=ht(Z);et=j&&!j.person?j.floor:null,o.domElement.style.cursor=j?"pointer":"grab"},mt=()=>{et=null};o.domElement.addEventListener("pointerdown",B),o.domElement.addEventListener("pointerup",at),o.domElement.addEventListener("pointermove",ut),o.domElement.addEventListener("pointerleave",mt),o.domElement.addEventListener("wheel",It,{passive:!0});let vt=Z=>Z.preventDefault();o.domElement.addEventListener("webglcontextlost",vt);let re=()=>Sn();o.domElement.addEventListener("webglcontextrestored",re);let Ft=0,Ce=performance.now(),De=0,Ke=0,sn=0,Mn=!0,ns=performance.now(),ir=!0,Pn=!0,vi=0,is=0,Ya=()=>G.some(Z=>[...Z.members.values()].some(j=>j.actor.state==="working"||j.actor.state==="answering"||j.actor.state==="arriving"||j.actor.state==="waiting")),Is=()=>{cancelAnimationFrame(Ft),window.clearTimeout(vi),Ft=0,vi=0};function Sn(){ns=performance.now(),ir=!0,i.dataset.sleeping="false",Ft===0&&Pn&&!nt&&!document.hidden&&(window.clearTimeout(vi),vi=0,Ce=performance.now(),Ft=requestAnimationFrame(zs))}let Ls=Z=>{if(Z<=50){Ft=requestAnimationFrame(zs);return}vi=window.setTimeout(()=>{vi=0,Ft===0&&Pn&&!nt&&!document.hidden&&(Ft=requestAnimationFrame(zs))},Z-16)},ta=Z=>lt?Lf:r==="backdrop"?Mn||Z<is?Uy:Fy:Mn||Z<Tt||Z<is?Lf:zy,zs=Z=>{if(Ft=0,nt||!Pn||document.hidden)return;let j=ta(Z);if(Z-De<j-2){Ls(j-(Z-De));return}De=Z;let dt=performance.now(),bt=Math.min(.05,(Z-Ce)/1e3)*l;Ce=Z;let _=Z/1e3,P=!1;if(!K)for(let O of G){xt(O,_);for(let k of O.members.values())k.person.update(bt,_,X),P||(P=k.person.walking);wt(O,_),O.room.aquarium.tick(_,bt,X)}Mn=rt(_)===!1||P||lt!==null,lt?pe(_):r==="backdrop"?Mn=Bt(bt)||Mn:f.update(),(Mn||ir||Z<is)&&(o.shadowMap.needsUpdate=!0,ir=!1),o.render(c,h),r==="room"&&Pt(),sn+=performance.now()-dt,Ke+=1,Ke>=60&&(i.dataset.drawCalls=String(o.info.render.calls),i.dataset.triangles=String(o.info.render.triangles),i.dataset.frameMs=(sn/Ke).toFixed(2),Ke=0,sn=0);let H=performance.now();(Mn||H<Tt||H<is||Ya()&&!K)&&(ns=H),H-ns<Dy?Ls(ta(H)):i.dataset.sleeping="true"},Za=()=>{document.hidden||Sn()};return document.addEventListener("visibilitychange",Za),Ft=requestAnimationFrame(zs),{update(Z){nt||(it(Z),Sn())},focus(Z){nt||!pt()||(tt=Z!==null&&N.has(Z)?Z:null,_e(performance.now()/1e3),Sn())},setPaused(Z){K=Z,Sn()},setModel(Z){let j=Sf(Z);if(j!==m){m=j;for(let dt of N.values())dt.room.aquarium.setFish(m);Sn()}},setMode(Z){nt||Z===r||(r=Z,i.dataset.mode=Z,f.enabled=!1,Et(),Ie(!0),Sn())},setActive(Z){nt||Z===Pn||(Pn=Z,i.dataset.active=String(Z),Pn?Sn():Is())},resetView(){Ie(!0),Sn()},exercise(Z){nt||(is=performance.now()+Z,Sn())},frame(){return o.shadowMap.needsUpdate=!0,o.render(c,h),o.domElement},calm(){return!Mn},dispose(){nt=!0,Is(),document.removeEventListener("visibilitychange",Za),Ht.disconnect(),o.domElement.removeEventListener("pointerdown",B),o.domElement.removeEventListener("pointerup",at),o.domElement.removeEventListener("pointermove",ut),o.domElement.removeEventListener("pointerleave",mt),o.domElement.removeEventListener("wheel",It),o.domElement.removeEventListener("webglcontextlost",vt),o.domElement.removeEventListener("webglcontextrestored",re),f.dispose();for(let Z of N.values())$(Z);N.clear(),G=[],R.removeFromParent(),C.removeFromParent();for(let Z of[R,C])Z.traverse(j=>{j instanceof kt&&j.geometry.dispose()});for(let Z of S)Z.geometry.dispose();z.removeFromParent(),z.geometry.dispose(),z.material.dispose(),U.dispose(),M.dispose(),Yl(x),o.dispose(),o.forceContextLoss(),o.domElement.remove()}}}var By=1e3/30,ky=1e3/12,Hy=4e3,Vy=1.1,Gy=.7,Qh=new F(-5,11,8),tu="__hover",Wy=6e4,nr=null,Ff=0;function eu({renderer:i,finishes:t}){Yl(t),i.dispose(),i.forceContextLoss()}function Xy(){window.clearTimeout(Ff);let i=nr;if(nr=null,i&&!i.renderer.getContext().isContextLost())return i;i&&eu(i);let t=new Vr({antialias:!0,alpha:!0,powerPreference:"low-power"});return t.shadowMap.enabled=!0,t.shadowMap.type=Zi,t.shadowMap.autoUpdate=!1,t.outputColorSpace=Ge,t.toneMapping=qs,t.domElement.classList.add("studio-canvas"),t.domElement.setAttribute("aria-hidden","true"),{renderer:t,finishes:ql()}}function qy(i){i.renderer.domElement.remove(),nr&&eu(nr),nr=i,Ff=window.setTimeout(()=>{nr===i&&(nr=null,eu(i))},Wy)}function Yy(i){return i<.5?4*i*i*i:1-(-2*i+2)**3/2}function Zy(i){return 1-(1-i)**3}function $y(i){return i*i*(2-i)}function Of(i,t,e,n,s){let r=performance.now(),a=Xy(),{renderer:l}=a;l.setPixelRatio(Math.min(window.devicePixelRatio||1,1.25)),l.toneMappingExposure=e.dark?1.05:1,l.domElement.style.cursor="",delete i.dataset.drawn,delete i.dataset.leaving,i.prepend(l.domElement);let o=new Bs,c=new Je(30,1,.5,260),h=new Kr(c,l.domElement);h.enableDamping=!0,h.dampingFactor=.08,h.enablePan=!1,h.rotateSpeed=.6,h.zoomSpeed=.8,o.add(new Gs(e.dark?"#9fb0e0":"#fff6ea",e.dark?"#3a3040":"#b8a48c",e.dark?1.35:1.5));let f=new Yi(e.dark?"#b9c8ff":"#fff1dc",e.dark?1.5:2.2);f.castShadow=!0,f.shadow.mapSize.set(1024,1024),f.shadow.camera.near=1,f.shadow.bias=-6e-4,f.shadow.radius=3,o.add(f,f.target);let d=new Yi(e.dark?"#5b4b8a":"#cfe3ff",e.dark?.35:.6);d.position.set(9,5,-3),o.add(d);let{finishes:p}=a,x=new se;o.add(x);let M=e.reducedMotion,m=[],u=n({root:x,finishes:p,options:e,still:M,pickable(B,at){B.traverse(ut=>{typeof at=="function"?ut.userData.pickInstance=at:ut.userData.pick=at}),m.push(B)}}),{min:b,max:A}=u.frame,v=new F((b.x+A.x)/2,(b.y+A.y)/2,(b.z+A.z)/2),S=Math.max(A.x-b.x,A.z-b.z)/2+2;f.target.position.copy(v),f.position.copy(Qh).multiplyScalar(1+S/Qh.length()).add(v),Object.assign(f.shadow.camera,{left:-S,right:S,top:S,bottom:-S,far:2*(Qh.length()+S)+10}),f.shadow.camera.updateProjectionMatrix();let E=(u.lamps??[]).map(B=>{let at=new Ti(B.colour??"#ffcf8a",e.dark?9:2.5,9,1.4);return at.position.set(B.x,B.y,B.z),o.add(at),at}),R=(B,at,ut)=>{let mt=new F().setFromSpherical(new zn(1,at,ut)),vt=new F(0,1,0).cross(mt).normalize(),re=mt.clone().cross(vt),Ft=Math.tan(ln.degToRad(c.fov)/2),Ce=Ft*c.aspect,De=new F,Ke=0;for(let sn=0;sn<8;sn+=1){De.set(sn&1?A.x:b.x,sn&2?A.y:b.y,sn&4?A.z:b.z).sub(B);let Mn=De.dot(mt);Ke=Math.max(Ke,Mn+Math.abs(De.dot(vt))/Ce,Mn+Math.abs(De.dot(re))/Ft)}return Ke},g=()=>{let B=c.aspect<1,at=B?Math.max(.45,u.frame.polar-.25):u.frame.polar;return{target:v.clone(),radius:R(v,at,u.frame.azimuth)*(B?.9:1.03),polar:at,azimuth:u.frame.azimuth}},w=()=>{let B=new zn().setFromVector3(c.position.clone().sub(h.target));return{target:h.target.clone(),radius:B.radius,polar:B.phi,azimuth:B.theta}},T=B=>{h.target.copy(B.target),c.position.setFromSpherical(new zn(B.radius,B.polar,B.azimuth)).add(B.target),c.lookAt(B.target)},C=()=>{let B=g();h.minDistance=B.radius*.4,h.maxDistance=B.radius*1.5,h.minPolarAngle=.3,h.maxPolarAngle=1.4,h.minAzimuthAngle=B.azimuth-1.1,h.maxAzimuthAngle=B.azimuth+1},D=null,V=!1,U=(B,at,ut,mt=Yy,vt=!1)=>{if(M||at<=0){T(B),h.update(),ut?.();return}D={from:w(),to:B,start:performance.now()/1e3,seconds:at,easing:mt,...vt?{arriving:vt}:{},...ut?{done:ut}:{}},h.enabled=!1},z=B=>{if(!D)return;let at=D.easing(Math.min(1,(B-D.start)/D.seconds)),{from:ut,to:mt}=D;if(T({target:ut.target.clone().lerp(mt.target,at),radius:ln.lerp(ut.radius,mt.radius,at),polar:ln.lerp(ut.polar,mt.polar,at),azimuth:ln.lerp(ut.azimuth,mt.azimuth,at)}),B-D.start>=D.seconds){let vt=D.done;D=null,h.enabled=!0,h.update(),vt?.()}},q=new Map,N=!0,G=performance.now(),X=4e3,K=B=>{let{actor:at,tag:ut,bubble:mt}=B;ut.dataset.state=at.state,ut.querySelector(".studio-tag-name").textContent=at.name,ut.querySelector(".studio-tag-state").textContent=at.stateLabel,ut.setAttribute("aria-label",`${at.name}: ${at.stateLabel}`),mt.textContent=at.bubble??"",mt.hidden=!at.bubble,mt.dataset.state=at.state},nt=B=>{let at=N||performance.now()-G<X,ut=at||!u.floor?B.place:u.floor.door,mt=new Jr(B.id,B.look,ut,e.accent,p);at&&(mt.heading=Math.atan2(B.place.face.x-B.place.x,B.place.face.z-B.place.z)),x.add(mt.root);let vt=document.createElement("button");vt.type="button",vt.className="studio-tag",vt.tabIndex=-1;for(let Ce of["studio-tag-dot","studio-tag-name","studio-tag-state"]){let De=document.createElement("span");De.className=Ce,vt.append(De)}vt.addEventListener("click",()=>{Ft.actor.pick&&s.pick(Ft.actor.pick)});let re=document.createElement("div");re.className="studio-bubble",t.append(re,vt);let Ft={person:mt,actor:B,tag:vt,bubble:re,key:""};return K(Ft),Ft},tt=B=>{B.person.dispose(),B.tag.remove(),B.bubble.remove()},lt=new Map,zt={},Lt=null,gt=B=>{for(let[at,ut]of lt)B[at]||(ut.element.remove(),lt.delete(at));for(let[at,ut]of Object.entries(B)){let mt=lt.get(at);if(!mt){let Ft=document.createElement("button");Ft.type="button",Ft.className="studio-floor-sign place-sign",Ft.tabIndex=-1;for(let Ce of["studio-floor-title","studio-floor-summary"]){let De=document.createElement("span");De.className=Ce,Ft.append(De)}Ft.addEventListener("click",()=>{let Ce=lt.get(at)?.label.pick;Ce&&s.pick(Ce)}),t.append(Ft),mt={element:Ft,label:ut,width:0,height:0},lt.set(at,mt)}mt.label=ut;let{element:vt}=mt;vt.dataset.busy=ut.tone==="busy"?"true":"false",vt.dataset.tone=ut.tone??"",vt.dataset.pick=ut.pick?"true":"false",vt.querySelector(".studio-floor-title").textContent=ut.title;let re=vt.querySelector(".studio-floor-summary");re.textContent=ut.detail??"",re.hidden=!ut.detail,vt.setAttribute("aria-label",ut.detail?`${ut.title}: ${ut.detail}`:ut.title),mt.width=vt.offsetWidth,mt.height=vt.offsetHeight}},J=!1,et=!1,pt=B=>{let at=performance.now()/1e3,{people:ut,labels:mt}=u.update(B,at),vt=new Set(ut.map(Ft=>Ft.id));for(let[Ft,Ce]of q)vt.has(Ft)||(tt(Ce),q.delete(Ft));for(let Ft of ut){let Ce=q.get(Ft.id);Ce?(Ce.actor.state!==Ft.state&&Ft.state==="done"&&Ce.person.cheer(at),Ce.actor=Ft,K(Ce)):q.set(Ft.id,nt(Ft))}N=!1,zt=mt;let re=Lt?u.hover?.(Lt)??null:null;gt(re?{...mt,[tu]:re}:mt)},At=new F,Mt=(B,at,ut)=>(At.set(B,at,ut).project(c),{x:(At.x*.5+.5)*i.clientWidth,y:(-At.y*.5+.5)*i.clientHeight,z:At.z,visible:At.z<1&&Math.abs(At.x)<1.15&&Math.abs(At.y)<1.15}),qt=()=>{for(let mt of q.values()){let vt=Mt(mt.person.position.x,mt.person.top+.12,mt.person.position.z),re=vt.visible;mt.tag.style.transform=`translate(${vt.x.toFixed(1)}px, ${vt.y.toFixed(1)}px) translate(-50%, -100%)`,mt.bubble.style.transform=`translate(${vt.x.toFixed(1)}px, ${(vt.y-30).toFixed(1)}px) translate(-50%, -100%)`,mt.tag.style.visibility=re?"visible":"hidden",mt.bubble.style.visibility=re?"visible":"hidden";let Ft=String(Math.round((1-vt.z)*1e4));mt.tag.style.zIndex=Ft,mt.bubble.style.zIndex=Ft}let B=(mt,vt)=>mt===tu?0:vt.label.tone==="alert"?1:vt.label.tone==="busy"?2:3,at=[...lt.entries()].map(([mt,vt])=>({id:mt,sign:vt,point:Mt(vt.label.at.x,vt.label.at.y,vt.label.at.z)})).sort((mt,vt)=>B(mt.id,mt.sign)-B(vt.id,vt.sign)||mt.point.z-vt.point.z),ut=[];for(let{sign:mt,point:vt}of at){let re=Math.max(8,Math.min(vt.x-mt.width/2,i.clientWidth-mt.width-8)),Ft=[re,vt.y-mt.height,re+mt.width,vt.y],Ce=!ut.some(([Ke,sn,Mn,ns])=>Ft[0]<Mn+3&&Ft[2]>Ke-3&&Ft[1]<ns+3&&Ft[3]>sn-3),De=vt.visible&&Ce;De&&ut.push(Ft),mt.element.style.transform=`translate(${re.toFixed(1)}px, ${vt.y.toFixed(1)}px) translate(0, -100%)`,mt.element.style.visibility=De?"visible":"hidden",mt.element.style.zIndex=String(Math.round((1-vt.z)*1e4))}t.dataset.moving=D?"true":"false"},ve=!1,Jt=!1,te=null,ne=()=>{!te||!Jt||(U(te,Vy,void 0,Zy,!0),te=null)},jt=()=>{let B=Math.max(1,i.clientWidth),at=Math.max(1,i.clientHeight);if(l.setSize(B,at,!1),c.aspect=B/at,c.updateProjectionMatrix(),!ve&&i.clientWidth>0){ve=!0;let ut=g();T({...ut,radius:ut.radius*1.25,polar:Math.max(.35,ut.polar-.12),azimuth:ut.azimuth+.22}),C(),te=ut,ne()}else ve&&!V&&(C(),D?.arriving?D.to=g():te?te=g():D||(T(g()),h.update()))},xe=new ResizeObserver(()=>{jt(),Wt()});xe.observe(i),jt();let ze=new Ws,Ie=new Xt,pe=null,_e=0,Y=B=>{if(D)return null;let at=l.domElement.getBoundingClientRect();Ie.set((B.clientX-at.left)/at.width*2-1,-((B.clientY-at.top)/at.height)*2+1),ze.setFromCamera(Ie,c);let ut=[...q.values()].map(mt=>mt.person.root);for(let mt of ze.intersectObjects([...ut,...m],!0)){let vt=mt.object.userData.personId,re=mt.object.userData.pickInstance,Ft=vt?q.get(vt)?.actor.pick:re&&mt.instanceId!==void 0?re(mt.instanceId):mt.object.userData.pick;if(Ft)return Ft}return null},Xe=B=>{pe={x:B.clientX,y:B.clientY},_e=performance.now()+1500,V=!0,Wt()},ye=B=>{if(pe&&Math.hypot(B.clientX-pe.x,B.clientY-pe.y)<5){let at=jh(t,B.clientX,B.clientY),ut=at?null:Y(B);at?at.click():ut&&s.pick(ut)}pe=null},L=B=>{if(B.buttons){_e=performance.now()+1500,Wt();return}let at=Y(B);if(l.domElement.style.cursor=at?"pointer":"grab",at!==Lt){Lt=at;let ut=at?u.hover?.(at)??null:null;gt(ut?{...zt,[tu]:ut}:zt)}},y=()=>{Lt!==null&&(Lt=null,gt(zt))},$=()=>{_e=performance.now()+1500,V=!0,Wt()},Q=B=>B.preventDefault();l.domElement.addEventListener("pointerdown",Xe),l.domElement.addEventListener("pointerup",ye),l.domElement.addEventListener("pointermove",L),l.domElement.addEventListener("pointerleave",y),l.domElement.addEventListener("wheel",$,{passive:!0}),l.domElement.addEventListener("webglcontextlost",Q);let it=()=>Wt();l.domElement.addEventListener("webglcontextrestored",it);let xt=0,wt=0,rt=performance.now(),ot=!0,St=0,Bt=0,Pt=performance.now(),Et=!0,Ht=()=>[...q.values()].some(B=>B.actor.state==="working"||B.actor.state==="waiting"),Vt=0;function Wt(){Pt=performance.now(),Et=!0,i.dataset.sleeping="false",xt===0&&!et&&!document.hidden&&Jt&&(window.clearTimeout(Vt),Vt=0,rt=performance.now(),xt=requestAnimationFrame(ht))}let W=B=>{if(B<=50){xt=requestAnimationFrame(ht);return}Vt=window.setTimeout(()=>{Vt=0,xt===0&&!et&&!document.hidden&&(xt=requestAnimationFrame(ht))},B-16)},Rt=B=>ot||B<_e||D?By:ky,ht=B=>{if(xt=0,et||document.hidden)return;let at=Rt(B);if(B-wt<at-2){W(at-(B-wt));return}wt=B;let ut=performance.now(),mt=Math.min(.05,(B-rt)/1e3);rt=B;let vt=B/1e3,re=!1;if(!J){for(let Ce of q.values()){let{actor:De,person:Ke}=Ce,sn=`${De.place.x.toFixed(2)},${De.place.z.toFixed(2)}`;sn!==Ce.key&&(Ce.key=sn,Ke.goTo(De.place,u.floor?u.floor.grid.path(Ke.position,De.place):[De.place])),Ke.action=De.action,Ke.update(mt,vt,M),re||(re=Ke.walking)}re=u.tick(vt,mt)||re}ot=re||D!==null,D?z(vt):h.update(),(ot||Et)&&(l.shadowMap.needsUpdate=!0,Et=!1),l.render(o,c),qt(),i.dataset.drawn!=="true"&&(i.dataset.drawn="true",i.dataset.firstFrameMs=String(Math.round(performance.now()-r))),Bt+=performance.now()-ut,St+=1,St>=60&&(i.dataset.drawCalls=String(l.info.render.calls),i.dataset.triangles=String(l.info.render.triangles),i.dataset.frameMs=(Bt/St).toFixed(2),St=0,Bt=0);let Ft=performance.now();(ot||Ft<_e||Ht()&&!J)&&(Pt=Ft),Ft-Pt<Hy?W(Rt(Ft)):i.dataset.sleeping="true"},Tt=()=>{document.hidden||Wt()};document.addEventListener("visibilitychange",Tt);let It=()=>{et||Jt||(Jt=!0,ne(),Wt())};return typeof l.compileAsync=="function"?l.compileAsync(o,c).then(It,It):It(),{update(B){et||(pt(B),Wt())},setPaused(B){J=B,Wt()},resetView(){U(g(),.9),Wt()},approach(B){let at=u.target?.(B);if(!at||et)return Promise.resolve();let ut=w();return Wt(),i.dataset.leaving="true",new Promise(mt=>U({target:new F(at.x,at.y,at.z),radius:ut.radius*.35,polar:Math.min(ut.polar+.15,1.3),azimuth:ut.azimuth},Gy,mt,$y))},dispose(){et=!0,cancelAnimationFrame(xt),window.clearTimeout(Vt),document.removeEventListener("visibilitychange",Tt),xe.disconnect(),l.domElement.removeEventListener("pointerdown",Xe),l.domElement.removeEventListener("pointerup",ye),l.domElement.removeEventListener("pointermove",L),l.domElement.removeEventListener("pointerleave",y),l.domElement.removeEventListener("wheel",$),l.domElement.removeEventListener("webglcontextlost",Q),l.domElement.removeEventListener("webglcontextrestored",it),h.dispose();for(let B of q.values())tt(B);q.clear();for(let B of lt.values())B.element.remove();lt.clear(),u.dispose();for(let B of E)B.dispose();f.dispose(),d.dispose(),x.removeFromParent(),qy(a)}}}var Ky={campus:Jd,library:mf,site:gf,duty:uf,desk:hf};window.AgentStudio={createStudioScene:Uf,createPlaceScene:Of,places:Ky};})();
