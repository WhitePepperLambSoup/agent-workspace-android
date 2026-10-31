(()=>{var df=Object.defineProperty;var ff=(i,t,e)=>t in i?df(i,t,{enumerable:!0,configurable:!0,writable:!0,value:e}):i[t]=e;var re=(i,t,e)=>ff(i,typeof t!="symbol"?t+"":t,e);/**
 * @license
 * Copyright 2010-2026 Three.js Authors
 * SPDX-License-Identifier: MIT
 */var ds={LEFT:0,MIDDLE:1,RIGHT:2,ROTATE:0,DOLLY:1,PAN:2},fs={ROTATE:0,PAN:1,DOLLY_PAN:2,DOLLY_ROTATE:3},du=0,Ac=1,fu=2;var Gi=1,pu=2,wr=3,ps=0,bn=1,vi=2,bi=0,Tr=1,Rc=2,Cc=3,Pc=4,mu=5;var Os=100,gu=101,xu=102,_u=103,yu=104,vu=200,bu=201,Mu=202,Su=203,Ic=204,Lc=205,Eu=206,wu=207,Tu=208,Au=209,Ru=210,Cu=211,Pu=212,Iu=213,Lu=214,lo=0,co=1,ho=2,fr=3,uo=4,fo=5,po=6,mo=7,Dc=0,Du=1,zu=2,si=0,zc=1,Nc=2,Uc=3,Bs=4,Fc=5,Oc=6,Bc=7;var kc=300,ms=301,ks=302,Bo=303,ko=304,va=306,gi=1e3,mi=1001,go=1002,tn=1003,Nu=1004;var ba=1005;var ln=1006,Ho=1007;var gs=1008;var An=1009,Hc=1010,Vc=1011,Ar=1012,Vo=1013,ri=1014,Vn=1015,ai=1016,Go=1017,Wo=1018,Rr=1020,Gc=35902,Wc=35899,Xc=1021,qc=1022,Gn=1023,xi=1026,xs=1027,Xo=1028,qo=1029,_s=1030,Yo=1031;var Zo=1033,Ma=33776,Sa=33777,Ea=33778,wa=33779,$o=35840,Ko=35841,Jo=35842,jo=35843,Qo=36196,tl=37492,el=37496,nl=37488,il=37489,Ta=37490,sl=37491,rl=37808,al=37809,ol=37810,ll=37811,cl=37812,hl=37813,ul=37814,dl=37815,fl=37816,pl=37817,ml=37818,gl=37819,xl=37820,_l=37821,yl=36492,vl=36494,bl=36495,Ml=36283,Sl=36284,Aa=36285,El=36286;var na=2300,xo=2301,ao=2302,_c=2303,yc=2400,vc=2401,bc=2402;var Uu=3200;var wl=0,Fu=1,Wi="",He="srgb",ia="srgb-linear",sa="linear",we="srgb";var oo=7680;var Ou=519,Bu=512,ku=513,Hu=514,Tl=515,Vu=516,Gu=517,Al=518,Wu=519,Xu=35044;var Yc="300 es",ni=2e3,pr=2001;function pf(i){for(let t=i.length-1;t>=0;--t)if(i[t]>=65535)return!0;return!1}function mf(i){return ArrayBuffer.isView(i)&&!(i instanceof DataView)}function ra(i){return document.createElementNS("http://www.w3.org/1999/xhtml",i)}function qu(){let i=ra("canvas");return i.style.display="block",i}var kh={},mr=null;function Zc(...i){let t="THREE."+i.shift();mr?mr("log",t,...i):console.log(t,...i)}function Yu(i){let t=i[0];if(typeof t=="string"&&t.startsWith("TSL:")){let e=i[1];e&&e.isStackTrace?i[0]+=" "+e.getLocation():i[1]='Stack trace not available. Enable "THREE.Node.captureStackTrace" to capture stack traces.'}return i}function Zt(...i){i=Yu(i);let t="THREE."+i.shift();if(mr)mr("warn",t,...i);else{let e=i[0];e&&e.isStackTrace?console.warn(e.getError(t)):console.warn(t,...i)}}function $t(...i){i=Yu(i);let t="THREE."+i.shift();if(mr)mr("error",t,...i);else{let e=i[0];e&&e.isStackTrace?console.error(e.getError(t)):console.error(t,...i)}}function Ls(...i){let t=i.join(" ");t in kh||(kh[t]=!0,Zt(...i))}function Zu(i,t,e){return new Promise(function(n,s){function r(){switch(i.clientWaitSync(t,i.SYNC_FLUSH_COMMANDS_BIT,0)){case i.WAIT_FAILED:s();break;case i.TIMEOUT_EXPIRED:setTimeout(r,e);break;default:n()}}setTimeout(r,e)})}var $u={[lo]:co,[ho]:po,[uo]:mo,[fr]:fo,[co]:lo,[po]:ho,[mo]:uo,[fo]:fr},ii=class{addEventListener(t,e){this._listeners===void 0&&(this._listeners={});let n=this._listeners;n[t]===void 0&&(n[t]=[]),n[t].indexOf(e)===-1&&n[t].push(e)}hasEventListener(t,e){let n=this._listeners;return n===void 0?!1:n[t]!==void 0&&n[t].indexOf(e)!==-1}removeEventListener(t,e){let n=this._listeners;if(n===void 0)return;let s=n[t];if(s!==void 0){let r=s.indexOf(e);r!==-1&&s.splice(r,1)}}dispatchEvent(t){let e=this._listeners;if(e===void 0)return;let n=e[t.type];if(n!==void 0){t.target=this;let s=n.slice(0);for(let r=0,a=s.length;r<a;r++)s[r].call(this,t);t.target=null}}},hn=["00","01","02","03","04","05","06","07","08","09","0a","0b","0c","0d","0e","0f","10","11","12","13","14","15","16","17","18","19","1a","1b","1c","1d","1e","1f","20","21","22","23","24","25","26","27","28","29","2a","2b","2c","2d","2e","2f","30","31","32","33","34","35","36","37","38","39","3a","3b","3c","3d","3e","3f","40","41","42","43","44","45","46","47","48","49","4a","4b","4c","4d","4e","4f","50","51","52","53","54","55","56","57","58","59","5a","5b","5c","5d","5e","5f","60","61","62","63","64","65","66","67","68","69","6a","6b","6c","6d","6e","6f","70","71","72","73","74","75","76","77","78","79","7a","7b","7c","7d","7e","7f","80","81","82","83","84","85","86","87","88","89","8a","8b","8c","8d","8e","8f","90","91","92","93","94","95","96","97","98","99","9a","9b","9c","9d","9e","9f","a0","a1","a2","a3","a4","a5","a6","a7","a8","a9","aa","ab","ac","ad","ae","af","b0","b1","b2","b3","b4","b5","b6","b7","b8","b9","ba","bb","bc","bd","be","bf","c0","c1","c2","c3","c4","c5","c6","c7","c8","c9","ca","cb","cc","cd","ce","cf","d0","d1","d2","d3","d4","d5","d6","d7","d8","d9","da","db","dc","dd","de","df","e0","e1","e2","e3","e4","e5","e6","e7","e8","e9","ea","eb","ec","ed","ee","ef","f0","f1","f2","f3","f4","f5","f6","f7","f8","f9","fa","fb","fc","fd","fe","ff"],Hh=1234567,ta=Math.PI/180,gr=180/Math.PI;function Cr(){let i=Math.random()*4294967295|0,t=Math.random()*4294967295|0,e=Math.random()*4294967295|0,n=Math.random()*4294967295|0;return(hn[i&255]+hn[i>>8&255]+hn[i>>16&255]+hn[i>>24&255]+"-"+hn[t&255]+hn[t>>8&255]+"-"+hn[t>>16&15|64]+hn[t>>24&255]+"-"+hn[e&63|128]+hn[e>>8&255]+"-"+hn[e>>16&255]+hn[e>>24&255]+hn[n&255]+hn[n>>8&255]+hn[n>>16&255]+hn[n>>24&255]).toLowerCase()}function he(i,t,e){return Math.max(t,Math.min(e,i))}function $c(i,t){return(i%t+t)%t}function gf(i,t,e,n,s){return n+(i-t)*(s-n)/(e-t)}function xf(i,t,e){return i!==t?(e-i)/(t-i):0}function ea(i,t,e){return(1-e)*i+e*t}function _f(i,t,e,n){return ea(i,t,1-Math.exp(-e*n))}function yf(i,t=1){return t-Math.abs($c(i,t*2)-t)}function vf(i,t,e){return i<=t?0:i>=e?1:(i=(i-t)/(e-t),i*i*(3-2*i))}function bf(i,t,e){return i<=t?0:i>=e?1:(i=(i-t)/(e-t),i*i*i*(i*(i*6-15)+10))}function Mf(i,t){return i+Math.floor(Math.random()*(t-i+1))}function Sf(i,t){return i+Math.random()*(t-i)}function Ef(i){return i*(.5-Math.random())}function wf(i){i!==void 0&&(Hh=i);let t=Hh+=1831565813;return t=Math.imul(t^t>>>15,t|1),t^=t+Math.imul(t^t>>>7,t|61),((t^t>>>14)>>>0)/4294967296}function Tf(i){return i*ta}function Af(i){return i*gr}function Rf(i){return i>0&&Number.isInteger(i)&&2**Math.round(Math.log2(i))===i}function Cf(i){return Math.pow(2,Math.ceil(Math.log(i)/Math.LN2))}function Pf(i){return Math.pow(2,Math.floor(Math.log(i)/Math.LN2))}function If(i,t,e,n,s){let r=Math.cos,a=Math.sin,o=r(e/2),l=a(e/2),c=r((t+n)/2),h=a((t+n)/2),p=r((t-n)/2),d=a((t-n)/2),f=r((n-t)/2),_=a((n-t)/2);switch(s){case"XYX":i.set(o*h,l*p,l*d,o*c);break;case"YZY":i.set(l*d,o*h,l*p,o*c);break;case"ZXZ":i.set(l*p,l*d,o*h,o*c);break;case"XZX":i.set(o*h,l*_,l*f,o*c);break;case"YXY":i.set(l*f,o*h,l*_,o*c);break;case"ZYZ":i.set(l*_,l*f,o*h,o*c);break;default:Zt("MathUtils: .setQuaternionFromProperEuler() encountered an unknown order: "+s)}}function ur(i,t){switch(t.constructor){case Float32Array:return i;case Uint32Array:return i/4294967295;case Uint16Array:return i/65535;case Uint8Array:case Uint8ClampedArray:return i/255;case Int32Array:return Math.max(i/2147483647,-1);case Int16Array:return Math.max(i/32767,-1);case Int8Array:return Math.max(i/127,-1);default:throw new Error("THREE.MathUtils: Invalid component type.")}}function yn(i,t){switch(t.constructor){case Float32Array:return i;case Uint32Array:return Math.round(i*4294967295);case Uint16Array:return Math.round(i*65535);case Uint8Array:case Uint8ClampedArray:return Math.round(i*255);case Int32Array:return Math.round(i*2147483647);case Int16Array:return Math.round(i*32767);case Int8Array:return Math.round(i*127);default:throw new Error("THREE.MathUtils: Invalid component type.")}}var en={DEG2RAD:ta,RAD2DEG:gr,generateUUID:Cr,clamp:he,euclideanModulo:$c,mapLinear:gf,inverseLerp:xf,lerp:ea,damp:_f,pingpong:yf,smoothstep:vf,smootherstep:bf,randInt:Mf,randFloat:Sf,randFloatSpread:Ef,seededRandom:wf,degToRad:Tf,radToDeg:Af,isPowerOfTwo:Rf,ceilPowerOfTwo:Cf,floorPowerOfTwo:Pf,setQuaternionFromProperEuler:If,normalize:yn,denormalize:ur},th=class th{constructor(t=0,e=0){this.x=t,this.y=e}get width(){return this.x}set width(t){this.x=t}get height(){return this.y}set height(t){this.y=t}set(t,e){return this.x=t,this.y=e,this}setScalar(t){return this.x=t,this.y=t,this}setX(t){return this.x=t,this}setY(t){return this.y=t,this}setComponent(t,e){switch(t){case 0:this.x=e;break;case 1:this.y=e;break;default:throw new Error("THREE.Vector2: index is out of range: "+t)}return this}getComponent(t){switch(t){case 0:return this.x;case 1:return this.y;default:throw new Error("THREE.Vector2: index is out of range: "+t)}}clone(){return new this.constructor(this.x,this.y)}copy(t){return this.x=t.x,this.y=t.y,this}add(t){return this.x+=t.x,this.y+=t.y,this}addScalar(t){return this.x+=t,this.y+=t,this}addVectors(t,e){return this.x=t.x+e.x,this.y=t.y+e.y,this}addScaledVector(t,e){return this.x+=t.x*e,this.y+=t.y*e,this}sub(t){return this.x-=t.x,this.y-=t.y,this}subScalar(t){return this.x-=t,this.y-=t,this}subVectors(t,e){return this.x=t.x-e.x,this.y=t.y-e.y,this}multiply(t){return this.x*=t.x,this.y*=t.y,this}multiplyScalar(t){return this.x*=t,this.y*=t,this}divide(t){return this.x/=t.x,this.y/=t.y,this}divideScalar(t){return this.multiplyScalar(1/t)}applyMatrix3(t){let e=this.x,n=this.y,s=t.elements;return this.x=s[0]*e+s[3]*n+s[6],this.y=s[1]*e+s[4]*n+s[7],this}min(t){return this.x=Math.min(this.x,t.x),this.y=Math.min(this.y,t.y),this}max(t){return this.x=Math.max(this.x,t.x),this.y=Math.max(this.y,t.y),this}clamp(t,e){return this.x=he(this.x,t.x,e.x),this.y=he(this.y,t.y,e.y),this}clampScalar(t,e){return this.x=he(this.x,t,e),this.y=he(this.y,t,e),this}clampLength(t,e){let n=this.length();return this.divideScalar(n||1).multiplyScalar(he(n,t,e))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this}negate(){return this.x=-this.x,this.y=-this.y,this}dot(t){return this.x*t.x+this.y*t.y}cross(t){return this.x*t.y-this.y*t.x}lengthSq(){return this.x*this.x+this.y*this.y}length(){return Math.sqrt(this.x*this.x+this.y*this.y)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)}normalize(){return this.divideScalar(this.length()||1)}angle(){return Math.atan2(-this.y,-this.x)+Math.PI}angleTo(t){let e=Math.sqrt(this.lengthSq()*t.lengthSq());if(e===0)return Math.PI/2;let n=this.dot(t)/e;return Math.acos(he(n,-1,1))}distanceTo(t){return Math.sqrt(this.distanceToSquared(t))}distanceToSquared(t){let e=this.x-t.x,n=this.y-t.y;return e*e+n*n}manhattanDistanceTo(t){return Math.abs(this.x-t.x)+Math.abs(this.y-t.y)}setLength(t){return this.normalize().multiplyScalar(t)}lerp(t,e){return this.x+=(t.x-this.x)*e,this.y+=(t.y-this.y)*e,this}lerpVectors(t,e,n){return this.x=t.x+(e.x-t.x)*n,this.y=t.y+(e.y-t.y)*n,this}equals(t){return t.x===this.x&&t.y===this.y}fromArray(t,e=0){return this.x=t[e],this.y=t[e+1],this}toArray(t=[],e=0){return t[e]=this.x,t[e+1]=this.y,t}fromBufferAttribute(t,e){return this.x=t.getX(e),this.y=t.getY(e),this}rotateAround(t,e){let n=Math.cos(e),s=Math.sin(e),r=this.x-t.x,a=this.y-t.y;return this.x=r*n-a*s+t.x,this.y=r*s+a*n+t.y,this}random(){return this.x=Math.random(),this.y=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y}};th.prototype.isVector2=!0;var qt=th,Xe=class{constructor(t=0,e=0,n=0,s=1){this.isQuaternion=!0,this._x=t,this._y=e,this._z=n,this._w=s}static slerpFlat(t,e,n,s,r,a,o){let l=n[s+0],c=n[s+1],h=n[s+2],p=n[s+3],d=r[a+0],f=r[a+1],_=r[a+2],b=r[a+3];if(p!==b||l!==d||c!==f||h!==_){let m=l*d+c*f+h*_+p*b;m<0&&(d=-d,f=-f,_=-_,b=-b,m=-m);let u=1-o;if(m<.9995){let S=Math.acos(m),R=Math.sin(S);u=Math.sin(u*S)/R,o=Math.sin(o*S)/R,l=l*u+d*o,c=c*u+f*o,h=h*u+_*o,p=p*u+b*o}else{l=l*u+d*o,c=c*u+f*o,h=h*u+_*o,p=p*u+b*o;let S=1/Math.sqrt(l*l+c*c+h*h+p*p);l*=S,c*=S,h*=S,p*=S}}t[e]=l,t[e+1]=c,t[e+2]=h,t[e+3]=p}static multiplyQuaternionsFlat(t,e,n,s,r,a){let o=n[s],l=n[s+1],c=n[s+2],h=n[s+3],p=r[a],d=r[a+1],f=r[a+2],_=r[a+3];return t[e]=o*_+h*p+l*f-c*d,t[e+1]=l*_+h*d+c*p-o*f,t[e+2]=c*_+h*f+o*d-l*p,t[e+3]=h*_-o*p-l*d-c*f,t}get x(){return this._x}set x(t){this._x=t,this._onChangeCallback()}get y(){return this._y}set y(t){this._y=t,this._onChangeCallback()}get z(){return this._z}set z(t){this._z=t,this._onChangeCallback()}get w(){return this._w}set w(t){this._w=t,this._onChangeCallback()}set(t,e,n,s){return this._x=t,this._y=e,this._z=n,this._w=s,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._w)}copy(t){return this._x=t.x,this._y=t.y,this._z=t.z,this._w=t.w,this._onChangeCallback(),this}setFromEuler(t,e=!0){let n=t._x,s=t._y,r=t._z,a=t._order,o=Math.cos,l=Math.sin,c=o(n/2),h=o(s/2),p=o(r/2),d=l(n/2),f=l(s/2),_=l(r/2);switch(a){case"XYZ":this._x=d*h*p+c*f*_,this._y=c*f*p-d*h*_,this._z=c*h*_+d*f*p,this._w=c*h*p-d*f*_;break;case"YXZ":this._x=d*h*p+c*f*_,this._y=c*f*p-d*h*_,this._z=c*h*_-d*f*p,this._w=c*h*p+d*f*_;break;case"ZXY":this._x=d*h*p-c*f*_,this._y=c*f*p+d*h*_,this._z=c*h*_+d*f*p,this._w=c*h*p-d*f*_;break;case"ZYX":this._x=d*h*p-c*f*_,this._y=c*f*p+d*h*_,this._z=c*h*_-d*f*p,this._w=c*h*p+d*f*_;break;case"YZX":this._x=d*h*p+c*f*_,this._y=c*f*p+d*h*_,this._z=c*h*_-d*f*p,this._w=c*h*p-d*f*_;break;case"XZY":this._x=d*h*p-c*f*_,this._y=c*f*p-d*h*_,this._z=c*h*_+d*f*p,this._w=c*h*p+d*f*_;break;default:Zt("Quaternion: .setFromEuler() encountered an unknown order: "+a)}return e===!0&&this._onChangeCallback(),this}setFromAxisAngle(t,e){let n=e/2,s=Math.sin(n);return this._x=t.x*s,this._y=t.y*s,this._z=t.z*s,this._w=Math.cos(n),this._onChangeCallback(),this}setFromRotationMatrix(t){let e=t.elements,n=e[0],s=e[4],r=e[8],a=e[1],o=e[5],l=e[9],c=e[2],h=e[6],p=e[10],d=n+o+p;if(d>0){let f=.5/Math.sqrt(d+1);this._w=.25/f,this._x=(h-l)*f,this._y=(r-c)*f,this._z=(a-s)*f}else if(n>o&&n>p){let f=2*Math.sqrt(1+n-o-p);this._w=(h-l)/f,this._x=.25*f,this._y=(s+a)/f,this._z=(r+c)/f}else if(o>p){let f=2*Math.sqrt(1+o-n-p);this._w=(r-c)/f,this._x=(s+a)/f,this._y=.25*f,this._z=(l+h)/f}else{let f=2*Math.sqrt(1+p-n-o);this._w=(a-s)/f,this._x=(r+c)/f,this._y=(l+h)/f,this._z=.25*f}return this._onChangeCallback(),this}setFromUnitVectors(t,e){let n=t.dot(e)+1;return n<1e-8?(n=0,Math.abs(t.x)>Math.abs(t.z)?(this._x=-t.y,this._y=t.x,this._z=0,this._w=n):(this._x=0,this._y=-t.z,this._z=t.y,this._w=n)):(this._x=t.y*e.z-t.z*e.y,this._y=t.z*e.x-t.x*e.z,this._z=t.x*e.y-t.y*e.x,this._w=n),this.normalize()}angleTo(t){return 2*Math.acos(Math.abs(he(this.dot(t),-1,1)))}rotateTowards(t,e){let n=this.angleTo(t);if(n===0)return this;let s=Math.min(1,e/n);return this.slerp(t,s),this}identity(){return this.set(0,0,0,1)}invert(){return this.conjugate()}conjugate(){return this._x*=-1,this._y*=-1,this._z*=-1,this._onChangeCallback(),this}dot(t){return this._x*t._x+this._y*t._y+this._z*t._z+this._w*t._w}lengthSq(){return this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w}length(){return Math.sqrt(this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w)}normalize(){let t=this.length();return t===0?(this._x=0,this._y=0,this._z=0,this._w=1):(t=1/t,this._x=this._x*t,this._y=this._y*t,this._z=this._z*t,this._w=this._w*t),this._onChangeCallback(),this}multiply(t){return this.multiplyQuaternions(this,t)}premultiply(t){return this.multiplyQuaternions(t,this)}multiplyQuaternions(t,e){let n=t._x,s=t._y,r=t._z,a=t._w,o=e._x,l=e._y,c=e._z,h=e._w;return this._x=n*h+a*o+s*c-r*l,this._y=s*h+a*l+r*o-n*c,this._z=r*h+a*c+n*l-s*o,this._w=a*h-n*o-s*l-r*c,this._onChangeCallback(),this}slerp(t,e){let n=t._x,s=t._y,r=t._z,a=t._w,o=this.dot(t);o<0&&(n=-n,s=-s,r=-r,a=-a,o=-o);let l=1-e;if(o<.9995){let c=Math.acos(o),h=Math.sin(c);l=Math.sin(l*c)/h,e=Math.sin(e*c)/h,this._x=this._x*l+n*e,this._y=this._y*l+s*e,this._z=this._z*l+r*e,this._w=this._w*l+a*e,this._onChangeCallback()}else this._x=this._x*l+n*e,this._y=this._y*l+s*e,this._z=this._z*l+r*e,this._w=this._w*l+a*e,this.normalize();return this}slerpQuaternions(t,e,n){return this.copy(t).slerp(e,n)}random(){let t=2*Math.PI*Math.random(),e=2*Math.PI*Math.random(),n=Math.random(),s=Math.sqrt(1-n),r=Math.sqrt(n);return this.set(s*Math.sin(t),s*Math.cos(t),r*Math.sin(e),r*Math.cos(e))}equals(t){return t._x===this._x&&t._y===this._y&&t._z===this._z&&t._w===this._w}fromArray(t,e=0){return this._x=t[e],this._y=t[e+1],this._z=t[e+2],this._w=t[e+3],this._onChangeCallback(),this}toArray(t=[],e=0){return t[e]=this._x,t[e+1]=this._y,t[e+2]=this._z,t[e+3]=this._w,t}fromBufferAttribute(t,e){return this._x=t.getX(e),this._y=t.getY(e),this._z=t.getZ(e),this._w=t.getW(e),this._onChangeCallback(),this}toJSON(){return this.toArray()}_onChange(t){return this._onChangeCallback=t,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._w}},eh=class eh{constructor(t=0,e=0,n=0){this.x=t,this.y=e,this.z=n}set(t,e,n){return n===void 0&&(n=this.z),this.x=t,this.y=e,this.z=n,this}setScalar(t){return this.x=t,this.y=t,this.z=t,this}setX(t){return this.x=t,this}setY(t){return this.y=t,this}setZ(t){return this.z=t,this}setComponent(t,e){switch(t){case 0:this.x=e;break;case 1:this.y=e;break;case 2:this.z=e;break;default:throw new Error("THREE.Vector3: index is out of range: "+t)}return this}getComponent(t){switch(t){case 0:return this.x;case 1:return this.y;case 2:return this.z;default:throw new Error("THREE.Vector3: index is out of range: "+t)}}clone(){return new this.constructor(this.x,this.y,this.z)}copy(t){return this.x=t.x,this.y=t.y,this.z=t.z,this}add(t){return this.x+=t.x,this.y+=t.y,this.z+=t.z,this}addScalar(t){return this.x+=t,this.y+=t,this.z+=t,this}addVectors(t,e){return this.x=t.x+e.x,this.y=t.y+e.y,this.z=t.z+e.z,this}addScaledVector(t,e){return this.x+=t.x*e,this.y+=t.y*e,this.z+=t.z*e,this}sub(t){return this.x-=t.x,this.y-=t.y,this.z-=t.z,this}subScalar(t){return this.x-=t,this.y-=t,this.z-=t,this}subVectors(t,e){return this.x=t.x-e.x,this.y=t.y-e.y,this.z=t.z-e.z,this}multiply(t){return this.x*=t.x,this.y*=t.y,this.z*=t.z,this}multiplyScalar(t){return this.x*=t,this.y*=t,this.z*=t,this}multiplyVectors(t,e){return this.x=t.x*e.x,this.y=t.y*e.y,this.z=t.z*e.z,this}applyEuler(t){return this.applyQuaternion(Vh.setFromEuler(t))}applyAxisAngle(t,e){return this.applyQuaternion(Vh.setFromAxisAngle(t,e))}applyMatrix3(t){let e=this.x,n=this.y,s=this.z,r=t.elements;return this.x=r[0]*e+r[3]*n+r[6]*s,this.y=r[1]*e+r[4]*n+r[7]*s,this.z=r[2]*e+r[5]*n+r[8]*s,this}applyNormalMatrix(t){return this.applyMatrix3(t).normalize()}applyMatrix4(t){let e=this.x,n=this.y,s=this.z,r=t.elements,a=1/(r[3]*e+r[7]*n+r[11]*s+r[15]);return this.x=(r[0]*e+r[4]*n+r[8]*s+r[12])*a,this.y=(r[1]*e+r[5]*n+r[9]*s+r[13])*a,this.z=(r[2]*e+r[6]*n+r[10]*s+r[14])*a,this}applyQuaternion(t){let e=this.x,n=this.y,s=this.z,r=t.x,a=t.y,o=t.z,l=t.w,c=2*(a*s-o*n),h=2*(o*e-r*s),p=2*(r*n-a*e);return this.x=e+l*c+a*p-o*h,this.y=n+l*h+o*c-r*p,this.z=s+l*p+r*h-a*c,this}project(t){return this.applyMatrix4(t.matrixWorldInverse).applyMatrix4(t.projectionMatrix)}unproject(t){return this.applyMatrix4(t.projectionMatrixInverse).applyMatrix4(t.matrixWorld)}transformDirection(t){let e=this.x,n=this.y,s=this.z,r=t.elements;return this.x=r[0]*e+r[4]*n+r[8]*s,this.y=r[1]*e+r[5]*n+r[9]*s,this.z=r[2]*e+r[6]*n+r[10]*s,this.normalize()}divide(t){return this.x/=t.x,this.y/=t.y,this.z/=t.z,this}divideScalar(t){return this.multiplyScalar(1/t)}min(t){return this.x=Math.min(this.x,t.x),this.y=Math.min(this.y,t.y),this.z=Math.min(this.z,t.z),this}max(t){return this.x=Math.max(this.x,t.x),this.y=Math.max(this.y,t.y),this.z=Math.max(this.z,t.z),this}clamp(t,e){return this.x=he(this.x,t.x,e.x),this.y=he(this.y,t.y,e.y),this.z=he(this.z,t.z,e.z),this}clampScalar(t,e){return this.x=he(this.x,t,e),this.y=he(this.y,t,e),this.z=he(this.z,t,e),this}clampLength(t,e){let n=this.length();return this.divideScalar(n||1).multiplyScalar(he(n,t,e))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this}dot(t){return this.x*t.x+this.y*t.y+this.z*t.z}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)}normalize(){return this.divideScalar(this.length()||1)}setLength(t){return this.normalize().multiplyScalar(t)}lerp(t,e){return this.x+=(t.x-this.x)*e,this.y+=(t.y-this.y)*e,this.z+=(t.z-this.z)*e,this}lerpVectors(t,e,n){return this.x=t.x+(e.x-t.x)*n,this.y=t.y+(e.y-t.y)*n,this.z=t.z+(e.z-t.z)*n,this}cross(t){return this.crossVectors(this,t)}crossVectors(t,e){let n=t.x,s=t.y,r=t.z,a=e.x,o=e.y,l=e.z;return this.x=s*l-r*o,this.y=r*a-n*l,this.z=n*o-s*a,this}projectOnVector(t){let e=t.lengthSq();if(e===0)return this.set(0,0,0);let n=t.dot(this)/e;return this.copy(t).multiplyScalar(n)}projectOnPlane(t){return Jl.copy(this).projectOnVector(t),this.sub(Jl)}reflect(t){return this.sub(Jl.copy(t).multiplyScalar(2*this.dot(t)))}angleTo(t){let e=Math.sqrt(this.lengthSq()*t.lengthSq());if(e===0)return Math.PI/2;let n=this.dot(t)/e;return Math.acos(he(n,-1,1))}distanceTo(t){return Math.sqrt(this.distanceToSquared(t))}distanceToSquared(t){let e=this.x-t.x,n=this.y-t.y,s=this.z-t.z;return e*e+n*n+s*s}manhattanDistanceTo(t){return Math.abs(this.x-t.x)+Math.abs(this.y-t.y)+Math.abs(this.z-t.z)}setFromSpherical(t){return this.setFromSphericalCoords(t.radius,t.phi,t.theta)}setFromSphericalCoords(t,e,n){let s=Math.sin(e)*t;return this.x=s*Math.sin(n),this.y=Math.cos(e)*t,this.z=s*Math.cos(n),this}setFromCylindrical(t){return this.setFromCylindricalCoords(t.radius,t.theta,t.y)}setFromCylindricalCoords(t,e,n){return this.x=t*Math.sin(e),this.y=n,this.z=t*Math.cos(e),this}setFromMatrixPosition(t){let e=t.elements;return this.x=e[12],this.y=e[13],this.z=e[14],this}setFromMatrixScale(t){let e=this.setFromMatrixColumn(t,0).length(),n=this.setFromMatrixColumn(t,1).length(),s=this.setFromMatrixColumn(t,2).length();return this.x=e,this.y=n,this.z=s,this}setFromMatrixColumn(t,e){return this.fromArray(t.elements,e*4)}setFromMatrix3Column(t,e){return this.fromArray(t.elements,e*3)}setFromEuler(t){return this.x=t._x,this.y=t._y,this.z=t._z,this}setFromColor(t){return this.x=t.r,this.y=t.g,this.z=t.b,this}equals(t){return t.x===this.x&&t.y===this.y&&t.z===this.z}fromArray(t,e=0){return this.x=t[e],this.y=t[e+1],this.z=t[e+2],this}toArray(t=[],e=0){return t[e]=this.x,t[e+1]=this.y,t[e+2]=this.z,t}fromBufferAttribute(t,e){return this.x=t.getX(e),this.y=t.getY(e),this.z=t.getZ(e),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this}randomDirection(){let t=Math.random()*Math.PI*2,e=Math.random()*2-1,n=Math.sqrt(1-e*e);return this.x=n*Math.cos(t),this.y=e,this.z=n*Math.sin(t),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z}};eh.prototype.isVector3=!0;var O=eh,Jl=new O,Vh=new Xe,nh=class nh{constructor(t,e,n,s,r,a,o,l,c){this.elements=[1,0,0,0,1,0,0,0,1],t!==void 0&&this.set(t,e,n,s,r,a,o,l,c)}set(t,e,n,s,r,a,o,l,c){let h=this.elements;return h[0]=t,h[1]=s,h[2]=o,h[3]=e,h[4]=r,h[5]=l,h[6]=n,h[7]=a,h[8]=c,this}identity(){return this.set(1,0,0,0,1,0,0,0,1),this}copy(t){let e=this.elements,n=t.elements;return e[0]=n[0],e[1]=n[1],e[2]=n[2],e[3]=n[3],e[4]=n[4],e[5]=n[5],e[6]=n[6],e[7]=n[7],e[8]=n[8],this}extractBasis(t,e,n){return t.setFromMatrix3Column(this,0),e.setFromMatrix3Column(this,1),n.setFromMatrix3Column(this,2),this}setFromMatrix4(t){let e=t.elements;return this.set(e[0],e[4],e[8],e[1],e[5],e[9],e[2],e[6],e[10]),this}multiply(t){return this.multiplyMatrices(this,t)}premultiply(t){return this.multiplyMatrices(t,this)}multiplyMatrices(t,e){let n=t.elements,s=e.elements,r=this.elements,a=n[0],o=n[3],l=n[6],c=n[1],h=n[4],p=n[7],d=n[2],f=n[5],_=n[8],b=s[0],m=s[3],u=s[6],S=s[1],R=s[4],v=s[7],M=s[2],E=s[5],A=s[8];return r[0]=a*b+o*S+l*M,r[3]=a*m+o*R+l*E,r[6]=a*u+o*v+l*A,r[1]=c*b+h*S+p*M,r[4]=c*m+h*R+p*E,r[7]=c*u+h*v+p*A,r[2]=d*b+f*S+_*M,r[5]=d*m+f*R+_*E,r[8]=d*u+f*v+_*A,this}multiplyScalar(t){let e=this.elements;return e[0]*=t,e[3]*=t,e[6]*=t,e[1]*=t,e[4]*=t,e[7]*=t,e[2]*=t,e[5]*=t,e[8]*=t,this}determinant(){let t=this.elements,e=t[0],n=t[1],s=t[2],r=t[3],a=t[4],o=t[5],l=t[6],c=t[7],h=t[8];return e*a*h-e*o*c-n*r*h+n*o*l+s*r*c-s*a*l}invert(){let t=this.elements,e=t[0],n=t[1],s=t[2],r=t[3],a=t[4],o=t[5],l=t[6],c=t[7],h=t[8],p=h*a-o*c,d=o*l-h*r,f=c*r-a*l,_=e*p+n*d+s*f;if(_===0)return this.set(0,0,0,0,0,0,0,0,0);let b=1/_;return t[0]=p*b,t[1]=(s*c-h*n)*b,t[2]=(o*n-s*a)*b,t[3]=d*b,t[4]=(h*e-s*l)*b,t[5]=(s*r-o*e)*b,t[6]=f*b,t[7]=(n*l-c*e)*b,t[8]=(a*e-n*r)*b,this}transpose(){let t,e=this.elements;return t=e[1],e[1]=e[3],e[3]=t,t=e[2],e[2]=e[6],e[6]=t,t=e[5],e[5]=e[7],e[7]=t,this}getNormalMatrix(t){return this.setFromMatrix4(t).invert().transpose()}transposeIntoArray(t){let e=this.elements;return t[0]=e[0],t[1]=e[3],t[2]=e[6],t[3]=e[1],t[4]=e[4],t[5]=e[7],t[6]=e[2],t[7]=e[5],t[8]=e[8],this}setUvTransform(t,e,n,s,r,a,o){let l=Math.cos(r),c=Math.sin(r);return this.set(n*l,n*c,-n*(l*a+c*o)+a+t,-s*c,s*l,-s*(-c*a+l*o)+o+e,0,0,1),this}scale(t,e){return Ls("Matrix3: .scale() is deprecated. Use .makeScale() instead."),this.premultiply(jl.makeScale(t,e)),this}rotate(t){return Ls("Matrix3: .rotate() is deprecated. Use .makeRotation() instead."),this.premultiply(jl.makeRotation(-t)),this}translate(t,e){return Ls("Matrix3: .translate() is deprecated. Use .makeTranslation() instead."),this.premultiply(jl.makeTranslation(t,e)),this}makeTranslation(t,e){return t.isVector2?this.set(1,0,t.x,0,1,t.y,0,0,1):this.set(1,0,t,0,1,e,0,0,1),this}makeRotation(t){let e=Math.cos(t),n=Math.sin(t);return this.set(e,-n,0,n,e,0,0,0,1),this}makeScale(t,e){return this.set(t,0,0,0,e,0,0,0,1),this}equals(t){let e=this.elements,n=t.elements;for(let s=0;s<9;s++)if(e[s]!==n[s])return!1;return!0}fromArray(t,e=0){for(let n=0;n<9;n++)this.elements[n]=t[n+e];return this}toArray(t=[],e=0){let n=this.elements;return t[e]=n[0],t[e+1]=n[1],t[e+2]=n[2],t[e+3]=n[3],t[e+4]=n[4],t[e+5]=n[5],t[e+6]=n[6],t[e+7]=n[7],t[e+8]=n[8],t}clone(){return new this.constructor().fromArray(this.elements)}};nh.prototype.isMatrix3=!0;var ee=nh,jl=new ee,Gh=new ee().set(.4123908,.3575843,.1804808,.212639,.7151687,.0721923,.0193308,.1191948,.9505322),Wh=new ee().set(3.2409699,-1.5373832,-.4986108,-.9692436,1.8759675,.0415551,.0556301,-.203977,1.0569715);function Lf(){let i={enabled:!0,workingColorSpace:ia,spaces:{},convert:function(s,r,a){return this.enabled===!1||r===a||!r||!a||(this.spaces[r].transfer===we&&(s.r=Bi(s.r),s.g=Bi(s.g),s.b=Bi(s.b)),this.spaces[r].primaries!==this.spaces[a].primaries&&(s.applyMatrix3(this.spaces[r].toXYZ),s.applyMatrix3(this.spaces[a].fromXYZ)),this.spaces[a].transfer===we&&(s.r=dr(s.r),s.g=dr(s.g),s.b=dr(s.b))),s},workingToColorSpace:function(s,r){return this.convert(s,this.workingColorSpace,r)},colorSpaceToWorking:function(s,r){return this.convert(s,r,this.workingColorSpace)},getPrimaries:function(s){return this.spaces[s].primaries},getTransfer:function(s){return s===Wi?sa:this.spaces[s].transfer},getToneMappingMode:function(s){return this.spaces[s].outputColorSpaceConfig.toneMappingMode||"standard"},getLuminanceCoefficients:function(s,r=this.workingColorSpace){return s.fromArray(this.spaces[r].luminanceCoefficients)},define:function(s){Object.assign(this.spaces,s)},_getMatrix:function(s,r,a){return s.copy(this.spaces[r].toXYZ).multiply(this.spaces[a].fromXYZ)},_getDrawingBufferColorSpace:function(s){return this.spaces[s].outputColorSpaceConfig.drawingBufferColorSpace},_getUnpackColorSpace:function(s=this.workingColorSpace){return this.spaces[s].workingColorSpaceConfig.unpackColorSpace},fromWorkingColorSpace:function(s,r){return Ls("ColorManagement: .fromWorkingColorSpace() has been renamed to .workingToColorSpace()."),i.workingToColorSpace(s,r)},toWorkingColorSpace:function(s,r){return Ls("ColorManagement: .toWorkingColorSpace() has been renamed to .colorSpaceToWorking()."),i.colorSpaceToWorking(s,r)}},t=[.64,.33,.3,.6,.15,.06],e=[.2126,.7152,.0722],n=[.3127,.329];return i.define({[ia]:{primaries:t,whitePoint:n,transfer:sa,toXYZ:Gh,fromXYZ:Wh,luminanceCoefficients:e,workingColorSpaceConfig:{unpackColorSpace:He},outputColorSpaceConfig:{drawingBufferColorSpace:He}},[He]:{primaries:t,whitePoint:n,transfer:we,toXYZ:Gh,fromXYZ:Wh,luminanceCoefficients:e,outputColorSpaceConfig:{drawingBufferColorSpace:He}}}),i}var me=Lf();function Bi(i){return i<.04045?i*.0773993808:Math.pow(i*.9478672986+.0521327014,2.4)}function dr(i){return i<.0031308?i*12.92:1.055*Math.pow(i,.41666)-.055}var Js,_o=class{static getDataURL(t,e="image/png"){if(/^data:/i.test(t.src)||typeof HTMLCanvasElement>"u")return t.src;let n;if(t instanceof HTMLCanvasElement)n=t;else{Js===void 0&&(Js=ra("canvas")),Js.width=t.width,Js.height=t.height;let s=Js.getContext("2d");t instanceof ImageData?s.putImageData(t,0,0):s.drawImage(t,0,0,t.width,t.height),n=Js}return n.toDataURL(e)}static sRGBToLinear(t){if(typeof HTMLImageElement<"u"&&t instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&t instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&t instanceof ImageBitmap){let e=ra("canvas");e.width=t.width,e.height=t.height;let n=e.getContext("2d");n.drawImage(t,0,0,t.width,t.height);let s=n.getImageData(0,0,t.width,t.height),r=s.data;for(let a=0;a<r.length;a++)r[a]=Bi(r[a]/255)*255;return n.putImageData(s,0,0),e}else if(t.data){let e=t.data.slice(0);for(let n=0;n<e.length;n++)e instanceof Uint8Array||e instanceof Uint8ClampedArray?e[n]=Math.floor(Bi(e[n]/255)*255):e[n]=Bi(e[n]);return{data:e,width:t.width,height:t.height}}else return Zt("ImageUtils.sRGBToLinear(): Unsupported image type. No color space conversion applied."),t}},Df=0,xr=class{constructor(t=null){this.isTextureSource=!0,Object.defineProperty(this,"id",{value:Df++}),this.uuid=Cr(),this.data=t,this.dataReady=!0,this.version=0}getSize(t){let e=this.data;return typeof HTMLVideoElement<"u"&&e instanceof HTMLVideoElement?t.set(e.videoWidth,e.videoHeight,0):typeof VideoFrame<"u"&&e instanceof VideoFrame?t.set(e.displayWidth,e.displayHeight,0):e!==null?t.set(e.width,e.height,e.depth||0):t.set(0,0,0),t}set needsUpdate(t){t===!0&&this.version++}toJSON(t){let e=t===void 0||typeof t=="string";if(!e&&t.images[this.uuid]!==void 0)return t.images[this.uuid];let n={uuid:this.uuid,url:""},s=this.data;if(s!==null){let r;if(Array.isArray(s)){r=[];for(let a=0,o=s.length;a<o;a++)s[a].isDataTexture?r.push(Ql(s[a].image)):r.push(Ql(s[a]))}else r=Ql(s);n.url=r}return e||(t.images[this.uuid]=n),n}};function Ql(i){return typeof HTMLImageElement<"u"&&i instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&i instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&i instanceof ImageBitmap?_o.getDataURL(i):i.data?{data:Array.from(i.data),width:i.width,height:i.height,type:i.data.constructor.name}:(Zt("Texture: Unable to serialize Texture."),{})}var zf=0,tc=new O,vn=class i extends ii{constructor(t=i.DEFAULT_IMAGE,e=i.DEFAULT_MAPPING,n=mi,s=mi,r=ln,a=gs,o=Gn,l=An,c=i.DEFAULT_ANISOTROPY,h=Wi){super(),this.isTexture=!0,Object.defineProperty(this,"id",{value:zf++}),this.uuid=Cr(),this.name="",this.source=new xr(t),this.mipmaps=[],this.mapping=e,this.channel=0,this.wrapS=n,this.wrapT=s,this.magFilter=r,this.minFilter=a,this.anisotropy=c,this.format=o,this.internalFormat=null,this.type=l,this.offset=new qt(0,0),this.repeat=new qt(1,1),this.center=new qt(0,0),this.rotation=0,this.matrixAutoUpdate=!0,this.matrix=new ee,this.generateMipmaps=!0,this.premultiplyAlpha=!1,this.flipY=!0,this.unpackAlignment=4,this.colorSpace=h,this.userData={},this.updateRanges=[],this.version=0,this.onUpdate=null,this.renderTarget=null,this.isRenderTargetTexture=!1,this.isArrayTexture=!!(t&&t.depth&&t.depth>1),this.pmremVersion=0,this.normalized=!1}get width(){return this.source.getSize(tc).x}get height(){return this.source.getSize(tc).y}get depth(){return this.source.getSize(tc).z}get image(){return this.source.data}set image(t){this.source.data=t}updateMatrix(){this.matrix.setUvTransform(this.offset.x,this.offset.y,this.repeat.x,this.repeat.y,this.rotation,this.center.x,this.center.y)}addUpdateRange(t,e){this.updateRanges.push({start:t,count:e})}clearUpdateRanges(){this.updateRanges.length=0}clone(){return new this.constructor().copy(this)}copy(t){return this.name=t.name,this.source=t.source,this.mipmaps=t.mipmaps.slice(0),this.mapping=t.mapping,this.channel=t.channel,this.wrapS=t.wrapS,this.wrapT=t.wrapT,this.magFilter=t.magFilter,this.minFilter=t.minFilter,this.anisotropy=t.anisotropy,this.format=t.format,this.internalFormat=t.internalFormat,this.type=t.type,this.normalized=t.normalized,this.offset.copy(t.offset),this.repeat.copy(t.repeat),this.center.copy(t.center),this.rotation=t.rotation,this.matrixAutoUpdate=t.matrixAutoUpdate,this.matrix.copy(t.matrix),this.generateMipmaps=t.generateMipmaps,this.premultiplyAlpha=t.premultiplyAlpha,this.flipY=t.flipY,this.unpackAlignment=t.unpackAlignment,this.colorSpace=t.colorSpace,this.renderTarget=t.renderTarget,this.isRenderTargetTexture=t.isRenderTargetTexture,this.isArrayTexture=t.isArrayTexture,this.userData=JSON.parse(JSON.stringify(t.userData)),this.needsUpdate=!0,this}setValues(t){for(let e in t){let n=t[e];if(n===void 0){Zt(`Texture.setValues(): parameter '${e}' has value of undefined.`);continue}let s=this[e];if(s===void 0){Zt(`Texture.setValues(): property '${e}' does not exist.`);continue}s&&n&&s.isVector2&&n.isVector2||s&&n&&s.isVector3&&n.isVector3||s&&n&&s.isMatrix3&&n.isMatrix3?s.copy(n):this[e]=n}}toJSON(t){let e=t===void 0||typeof t=="string";if(!e&&t.textures[this.uuid]!==void 0)return t.textures[this.uuid];let n={metadata:{version:4.7,type:"Texture",generator:"Texture.toJSON"},uuid:this.uuid,name:this.name,image:this.source.toJSON(t).uuid,mapping:this.mapping,channel:this.channel,repeat:[this.repeat.x,this.repeat.y],offset:[this.offset.x,this.offset.y],center:[this.center.x,this.center.y],rotation:this.rotation,wrap:[this.wrapS,this.wrapT],format:this.format,internalFormat:this.internalFormat,type:this.type,normalized:this.normalized,colorSpace:this.colorSpace,minFilter:this.minFilter,magFilter:this.magFilter,anisotropy:this.anisotropy,flipY:this.flipY,generateMipmaps:this.generateMipmaps,premultiplyAlpha:this.premultiplyAlpha,unpackAlignment:this.unpackAlignment};return Object.keys(this.userData).length>0&&(n.userData=this.userData),e||(t.textures[this.uuid]=n),n}dispose(){this.dispatchEvent({type:"dispose"})}transformUv(t){if(this.mapping!==kc)return t;if(t.applyMatrix3(this.matrix),t.x<0||t.x>1)switch(this.wrapS){case gi:t.x=t.x-Math.floor(t.x);break;case mi:t.x=t.x<0?0:1;break;case go:Math.abs(Math.floor(t.x)%2)===1?t.x=Math.ceil(t.x)-t.x:t.x=t.x-Math.floor(t.x);break}if(t.y<0||t.y>1)switch(this.wrapT){case gi:t.y=t.y-Math.floor(t.y);break;case mi:t.y=t.y<0?0:1;break;case go:Math.abs(Math.floor(t.y)%2)===1?t.y=Math.ceil(t.y)-t.y:t.y=t.y-Math.floor(t.y);break}return this.flipY&&(t.y=1-t.y),t}set needsUpdate(t){t===!0&&(this.version++,this.source.needsUpdate=!0)}set needsPMREMUpdate(t){t===!0&&this.pmremVersion++}};vn.DEFAULT_IMAGE=null;vn.DEFAULT_MAPPING=kc;vn.DEFAULT_ANISOTROPY=1;var ih=class ih{constructor(t=0,e=0,n=0,s=1){this.x=t,this.y=e,this.z=n,this.w=s}get width(){return this.z}set width(t){this.z=t}get height(){return this.w}set height(t){this.w=t}set(t,e,n,s){return this.x=t,this.y=e,this.z=n,this.w=s,this}setScalar(t){return this.x=t,this.y=t,this.z=t,this.w=t,this}setX(t){return this.x=t,this}setY(t){return this.y=t,this}setZ(t){return this.z=t,this}setW(t){return this.w=t,this}setComponent(t,e){switch(t){case 0:this.x=e;break;case 1:this.y=e;break;case 2:this.z=e;break;case 3:this.w=e;break;default:throw new Error("THREE.Vector4: index is out of range: "+t)}return this}getComponent(t){switch(t){case 0:return this.x;case 1:return this.y;case 2:return this.z;case 3:return this.w;default:throw new Error("THREE.Vector4: index is out of range: "+t)}}clone(){return new this.constructor(this.x,this.y,this.z,this.w)}copy(t){return this.x=t.x,this.y=t.y,this.z=t.z,this.w=t.w!==void 0?t.w:1,this}add(t){return this.x+=t.x,this.y+=t.y,this.z+=t.z,this.w+=t.w,this}addScalar(t){return this.x+=t,this.y+=t,this.z+=t,this.w+=t,this}addVectors(t,e){return this.x=t.x+e.x,this.y=t.y+e.y,this.z=t.z+e.z,this.w=t.w+e.w,this}addScaledVector(t,e){return this.x+=t.x*e,this.y+=t.y*e,this.z+=t.z*e,this.w+=t.w*e,this}sub(t){return this.x-=t.x,this.y-=t.y,this.z-=t.z,this.w-=t.w,this}subScalar(t){return this.x-=t,this.y-=t,this.z-=t,this.w-=t,this}subVectors(t,e){return this.x=t.x-e.x,this.y=t.y-e.y,this.z=t.z-e.z,this.w=t.w-e.w,this}multiply(t){return this.x*=t.x,this.y*=t.y,this.z*=t.z,this.w*=t.w,this}multiplyScalar(t){return this.x*=t,this.y*=t,this.z*=t,this.w*=t,this}applyMatrix4(t){let e=this.x,n=this.y,s=this.z,r=this.w,a=t.elements;return this.x=a[0]*e+a[4]*n+a[8]*s+a[12]*r,this.y=a[1]*e+a[5]*n+a[9]*s+a[13]*r,this.z=a[2]*e+a[6]*n+a[10]*s+a[14]*r,this.w=a[3]*e+a[7]*n+a[11]*s+a[15]*r,this}divide(t){return this.x/=t.x,this.y/=t.y,this.z/=t.z,this.w/=t.w,this}divideScalar(t){return this.multiplyScalar(1/t)}setAxisAngleFromQuaternion(t){this.w=2*Math.acos(t.w);let e=Math.sqrt(1-t.w*t.w);return e<1e-4?(this.x=1,this.y=0,this.z=0):(this.x=t.x/e,this.y=t.y/e,this.z=t.z/e),this}setAxisAngleFromRotationMatrix(t){let e,n,s,r,l=t.elements,c=l[0],h=l[4],p=l[8],d=l[1],f=l[5],_=l[9],b=l[2],m=l[6],u=l[10];if(Math.abs(h-d)<.01&&Math.abs(p-b)<.01&&Math.abs(_-m)<.01){if(Math.abs(h+d)<.1&&Math.abs(p+b)<.1&&Math.abs(_+m)<.1&&Math.abs(c+f+u-3)<.1)return this.set(1,0,0,0),this;e=Math.PI;let R=(c+1)/2,v=(f+1)/2,M=(u+1)/2,E=(h+d)/4,A=(p+b)/4,g=(_+m)/4;return R>v&&R>M?R<.01?(n=0,s=.707106781,r=.707106781):(n=Math.sqrt(R),s=E/n,r=A/n):v>M?v<.01?(n=.707106781,s=0,r=.707106781):(s=Math.sqrt(v),n=E/s,r=g/s):M<.01?(n=.707106781,s=.707106781,r=0):(r=Math.sqrt(M),n=A/r,s=g/r),this.set(n,s,r,e),this}let S=Math.sqrt((m-_)*(m-_)+(p-b)*(p-b)+(d-h)*(d-h));return Math.abs(S)<.001&&(S=1),this.x=(m-_)/S,this.y=(p-b)/S,this.z=(d-h)/S,this.w=Math.acos((c+f+u-1)/2),this}setFromMatrixPosition(t){let e=t.elements;return this.x=e[12],this.y=e[13],this.z=e[14],this.w=e[15],this}min(t){return this.x=Math.min(this.x,t.x),this.y=Math.min(this.y,t.y),this.z=Math.min(this.z,t.z),this.w=Math.min(this.w,t.w),this}max(t){return this.x=Math.max(this.x,t.x),this.y=Math.max(this.y,t.y),this.z=Math.max(this.z,t.z),this.w=Math.max(this.w,t.w),this}clamp(t,e){return this.x=he(this.x,t.x,e.x),this.y=he(this.y,t.y,e.y),this.z=he(this.z,t.z,e.z),this.w=he(this.w,t.w,e.w),this}clampScalar(t,e){return this.x=he(this.x,t,e),this.y=he(this.y,t,e),this.z=he(this.z,t,e),this.w=he(this.w,t,e),this}clampLength(t,e){let n=this.length();return this.divideScalar(n||1).multiplyScalar(he(n,t,e))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this.w=Math.floor(this.w),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this.w=Math.ceil(this.w),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this.w=Math.round(this.w),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this.w=Math.trunc(this.w),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this.w=-this.w,this}dot(t){return this.x*t.x+this.y*t.y+this.z*t.z+this.w*t.w}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)+Math.abs(this.w)}normalize(){return this.divideScalar(this.length()||1)}setLength(t){return this.normalize().multiplyScalar(t)}lerp(t,e){return this.x+=(t.x-this.x)*e,this.y+=(t.y-this.y)*e,this.z+=(t.z-this.z)*e,this.w+=(t.w-this.w)*e,this}lerpVectors(t,e,n){return this.x=t.x+(e.x-t.x)*n,this.y=t.y+(e.y-t.y)*n,this.z=t.z+(e.z-t.z)*n,this.w=t.w+(e.w-t.w)*n,this}equals(t){return t.x===this.x&&t.y===this.y&&t.z===this.z&&t.w===this.w}fromArray(t,e=0){return this.x=t[e],this.y=t[e+1],this.z=t[e+2],this.w=t[e+3],this}toArray(t=[],e=0){return t[e]=this.x,t[e+1]=this.y,t[e+2]=this.z,t[e+3]=this.w,t}fromBufferAttribute(t,e){return this.x=t.getX(e),this.y=t.getY(e),this.z=t.getZ(e),this.w=t.getW(e),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this.w=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z,yield this.w}};ih.prototype.isVector4=!0;var Oe=ih,yo=class extends ii{constructor(t=1,e=1,n={}){super(),n=Object.assign({generateMipmaps:!1,internalFormat:null,minFilter:ln,depthBuffer:!0,stencilBuffer:!1,resolveColorBuffer:!0,resolveDepthBuffer:!0,resolveStencilBuffer:!0,storeMultisampledColorBuffer:!0,storeMultisampledDepthBuffer:!0,storeMultisampledStencilBuffer:!0,depthTexture:null,samples:0,count:1,depth:1,multiview:!1,useArrayDepthTexture:!1},n),this.isRenderTarget=!0,this.width=t,this.height=e,this.depth=n.depth,this.scissor=new Oe(0,0,t,e),this.scissorTest=!1,this.viewport=new Oe(0,0,t,e),this.textures=[];let s={width:t,height:e,depth:n.depth},r=new vn(s),a=n.count;for(let o=0;o<a;o++)this.textures[o]=r.clone(),this.textures[o].isRenderTargetTexture=!0,this.textures[o].renderTarget=this;this._setTextureOptions(n),this.depthBuffer=n.depthBuffer,this.stencilBuffer=n.stencilBuffer,this.resolveColorBuffer=n.resolveColorBuffer,this.resolveDepthBuffer=n.resolveDepthBuffer,this.resolveStencilBuffer=n.resolveStencilBuffer,this.storeMultisampledColorBuffer=n.storeMultisampledColorBuffer,this.storeMultisampledDepthBuffer=n.storeMultisampledDepthBuffer,this.storeMultisampledStencilBuffer=n.storeMultisampledStencilBuffer,this._depthTexture=null,this.depthTexture=n.depthTexture,this.samples=n.samples,this.multiview=n.multiview,this.useArrayDepthTexture=n.useArrayDepthTexture}_setTextureOptions(t={}){let e={minFilter:ln,generateMipmaps:!1,flipY:!1,internalFormat:null};t.mapping!==void 0&&(e.mapping=t.mapping),t.wrapS!==void 0&&(e.wrapS=t.wrapS),t.wrapT!==void 0&&(e.wrapT=t.wrapT),t.wrapR!==void 0&&(e.wrapR=t.wrapR),t.magFilter!==void 0&&(e.magFilter=t.magFilter),t.minFilter!==void 0&&(e.minFilter=t.minFilter),t.format!==void 0&&(e.format=t.format),t.type!==void 0&&(e.type=t.type),t.anisotropy!==void 0&&(e.anisotropy=t.anisotropy),t.colorSpace!==void 0&&(e.colorSpace=t.colorSpace),t.flipY!==void 0&&(e.flipY=t.flipY),t.generateMipmaps!==void 0&&(e.generateMipmaps=t.generateMipmaps),t.internalFormat!==void 0&&(e.internalFormat=t.internalFormat);for(let n=0;n<this.textures.length;n++)this.textures[n].setValues(e)}get texture(){return this.textures[0]}set texture(t){this.textures[0]=t}set depthTexture(t){this._depthTexture!==null&&this._depthTexture.renderTarget===this&&(this._depthTexture.renderTarget=null),t!==null&&t.renderTarget===null&&(t.renderTarget=this),this._depthTexture=t}get depthTexture(){return this._depthTexture}setSize(t,e,n=1){if(this.width!==t||this.height!==e||this.depth!==n){this.width=t,this.height=e,this.depth=n;for(let s=0,r=this.textures.length;s<r;s++)this.textures[s].image.width=t,this.textures[s].image.height=e,this.textures[s].image.depth=n,this.textures[s].isData3DTexture!==!0&&(this.textures[s].isArrayTexture=this.textures[s].image.depth>1);this.dispose()}this.viewport.set(0,0,t,e),this.scissor.set(0,0,t,e)}clone(){return new this.constructor().copy(this)}copy(t){this.width=t.width,this.height=t.height,this.depth=t.depth,this.scissor.copy(t.scissor),this.scissorTest=t.scissorTest,this.viewport.copy(t.viewport),this.textures.length=0;for(let e=0,n=t.textures.length;e<n;e++){this.textures[e]=t.textures[e].clone(),this.textures[e].isRenderTargetTexture=!0,this.textures[e].renderTarget=this;let s=Object.assign({},t.textures[e].image);this.textures[e].source=new xr(s)}if(this.depthBuffer=t.depthBuffer,this.stencilBuffer=t.stencilBuffer,this.resolveColorBuffer=t.resolveColorBuffer,this.resolveDepthBuffer=t.resolveDepthBuffer,this.resolveStencilBuffer=t.resolveStencilBuffer,this.storeMultisampledColorBuffer=t.storeMultisampledColorBuffer,this.storeMultisampledDepthBuffer=t.storeMultisampledDepthBuffer,this.storeMultisampledStencilBuffer=t.storeMultisampledStencilBuffer,t.depthTexture!==null)if(t.depthTexture.renderTarget===t){let e=t.depthTexture.clone();e.renderTarget=null,this.depthTexture=e}else this.depthTexture=t.depthTexture;return this.samples=t.samples,this.multiview=t.multiview,this.useArrayDepthTexture=t.useArrayDepthTexture,this}dispose(){this.dispatchEvent({type:"dispose"})}},wn=class extends yo{constructor(t=1,e=1,n={}){super(t,e,n),this.isWebGLRenderTarget=!0}},aa=class extends vn{constructor(t=null,e=1,n=1,s=1){super(null),this.isDataArrayTexture=!0,this.image={data:t,width:e,height:n,depth:s},this.magFilter=tn,this.minFilter=tn,this.wrapR=mi,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1,this.layerUpdates=new Set}copy(t){return super.copy(t),this.wrapR=t.wrapR,this}addLayerUpdate(t){this.layerUpdates.add(t)}clearLayerUpdates(){this.layerUpdates.clear()}};var vo=class extends vn{constructor(t=null,e=1,n=1,s=1){super(null),this.isData3DTexture=!0,this.image={data:t,width:e,height:n,depth:s},this.magFilter=tn,this.minFilter=tn,this.wrapR=mi,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}copy(t){return super.copy(t),this.wrapR=t.wrapR,this}};var Oo=class Oo{constructor(t,e,n,s,r,a,o,l,c,h,p,d,f,_,b,m){this.elements=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],t!==void 0&&this.set(t,e,n,s,r,a,o,l,c,h,p,d,f,_,b,m)}set(t,e,n,s,r,a,o,l,c,h,p,d,f,_,b,m){let u=this.elements;return u[0]=t,u[4]=e,u[8]=n,u[12]=s,u[1]=r,u[5]=a,u[9]=o,u[13]=l,u[2]=c,u[6]=h,u[10]=p,u[14]=d,u[3]=f,u[7]=_,u[11]=b,u[15]=m,this}identity(){return this.set(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1),this}clone(){return new Oo().fromArray(this.elements)}copy(t){let e=this.elements,n=t.elements;return e[0]=n[0],e[1]=n[1],e[2]=n[2],e[3]=n[3],e[4]=n[4],e[5]=n[5],e[6]=n[6],e[7]=n[7],e[8]=n[8],e[9]=n[9],e[10]=n[10],e[11]=n[11],e[12]=n[12],e[13]=n[13],e[14]=n[14],e[15]=n[15],this}copyPosition(t){let e=this.elements,n=t.elements;return e[12]=n[12],e[13]=n[13],e[14]=n[14],this}setFromMatrix3(t){let e=t.elements;return this.set(e[0],e[3],e[6],0,e[1],e[4],e[7],0,e[2],e[5],e[8],0,0,0,0,1),this}extractBasis(t,e,n){return this.determinantAffine()===0?(t.set(1,0,0),e.set(0,1,0),n.set(0,0,1),this):(t.setFromMatrixColumn(this,0),e.setFromMatrixColumn(this,1),n.setFromMatrixColumn(this,2),this)}makeBasis(t,e,n){return this.set(t.x,e.x,n.x,0,t.y,e.y,n.y,0,t.z,e.z,n.z,0,0,0,0,1),this}extractRotation(t){if(t.determinantAffine()===0)return this.identity();let e=this.elements,n=t.elements,s=1/js.setFromMatrixColumn(t,0).length(),r=1/js.setFromMatrixColumn(t,1).length(),a=1/js.setFromMatrixColumn(t,2).length();return e[0]=n[0]*s,e[1]=n[1]*s,e[2]=n[2]*s,e[3]=0,e[4]=n[4]*r,e[5]=n[5]*r,e[6]=n[6]*r,e[7]=0,e[8]=n[8]*a,e[9]=n[9]*a,e[10]=n[10]*a,e[11]=0,e[12]=0,e[13]=0,e[14]=0,e[15]=1,this}makeRotationFromEuler(t){let e=this.elements,n=t.x,s=t.y,r=t.z,a=Math.cos(n),o=Math.sin(n),l=Math.cos(s),c=Math.sin(s),h=Math.cos(r),p=Math.sin(r);if(t.order==="XYZ"){let d=a*h,f=a*p,_=o*h,b=o*p;e[0]=l*h,e[4]=-l*p,e[8]=c,e[1]=f+_*c,e[5]=d-b*c,e[9]=-o*l,e[2]=b-d*c,e[6]=_+f*c,e[10]=a*l}else if(t.order==="YXZ"){let d=l*h,f=l*p,_=c*h,b=c*p;e[0]=d+b*o,e[4]=_*o-f,e[8]=a*c,e[1]=a*p,e[5]=a*h,e[9]=-o,e[2]=f*o-_,e[6]=b+d*o,e[10]=a*l}else if(t.order==="ZXY"){let d=l*h,f=l*p,_=c*h,b=c*p;e[0]=d-b*o,e[4]=-a*p,e[8]=_+f*o,e[1]=f+_*o,e[5]=a*h,e[9]=b-d*o,e[2]=-a*c,e[6]=o,e[10]=a*l}else if(t.order==="ZYX"){let d=a*h,f=a*p,_=o*h,b=o*p;e[0]=l*h,e[4]=_*c-f,e[8]=d*c+b,e[1]=l*p,e[5]=b*c+d,e[9]=f*c-_,e[2]=-c,e[6]=o*l,e[10]=a*l}else if(t.order==="YZX"){let d=a*l,f=a*c,_=o*l,b=o*c;e[0]=l*h,e[4]=b-d*p,e[8]=_*p+f,e[1]=p,e[5]=a*h,e[9]=-o*h,e[2]=-c*h,e[6]=f*p+_,e[10]=d-b*p}else if(t.order==="XZY"){let d=a*l,f=a*c,_=o*l,b=o*c;e[0]=l*h,e[4]=-p,e[8]=c*h,e[1]=d*p+b,e[5]=a*h,e[9]=f*p-_,e[2]=_*p-f,e[6]=o*h,e[10]=b*p+d}return e[3]=0,e[7]=0,e[11]=0,e[12]=0,e[13]=0,e[14]=0,e[15]=1,this}makeRotationFromQuaternion(t){return this.compose(Nf,t,Uf)}lookAt(t,e,n){let s=this.elements;return In.subVectors(t,e),In.lengthSq()===0&&(In.z=1),In.normalize(),ts.crossVectors(n,In),ts.lengthSq()===0&&(Math.abs(n.z)===1?In.x+=1e-4:In.z+=1e-4,In.normalize(),ts.crossVectors(n,In)),ts.normalize(),ka.crossVectors(In,ts),s[0]=ts.x,s[4]=ka.x,s[8]=In.x,s[1]=ts.y,s[5]=ka.y,s[9]=In.y,s[2]=ts.z,s[6]=ka.z,s[10]=In.z,this}multiply(t){return this.multiplyMatrices(this,t)}premultiply(t){return this.multiplyMatrices(t,this)}multiplyMatrices(t,e){let n=t.elements,s=e.elements,r=this.elements,a=n[0],o=n[4],l=n[8],c=n[12],h=n[1],p=n[5],d=n[9],f=n[13],_=n[2],b=n[6],m=n[10],u=n[14],S=n[3],R=n[7],v=n[11],M=n[15],E=s[0],A=s[4],g=s[8],w=s[12],T=s[1],I=s[5],N=s[9],B=s[13],F=s[2],P=s[6],V=s[10],z=s[14],X=s[3],G=s[7],Y=s[11],tt=s[15];return r[0]=a*E+o*T+l*F+c*X,r[4]=a*A+o*I+l*P+c*G,r[8]=a*g+o*N+l*V+c*Y,r[12]=a*w+o*B+l*z+c*tt,r[1]=h*E+p*T+d*F+f*X,r[5]=h*A+p*I+d*P+f*G,r[9]=h*g+p*N+d*V+f*Y,r[13]=h*w+p*B+d*z+f*tt,r[2]=_*E+b*T+m*F+u*X,r[6]=_*A+b*I+m*P+u*G,r[10]=_*g+b*N+m*V+u*Y,r[14]=_*w+b*B+m*z+u*tt,r[3]=S*E+R*T+v*F+M*X,r[7]=S*A+R*I+v*P+M*G,r[11]=S*g+R*N+v*V+M*Y,r[15]=S*w+R*B+v*z+M*tt,this}multiplyScalar(t){let e=this.elements;return e[0]*=t,e[4]*=t,e[8]*=t,e[12]*=t,e[1]*=t,e[5]*=t,e[9]*=t,e[13]*=t,e[2]*=t,e[6]*=t,e[10]*=t,e[14]*=t,e[3]*=t,e[7]*=t,e[11]*=t,e[15]*=t,this}determinant(){let t=this.elements,e=t[0],n=t[4],s=t[8],r=t[12],a=t[1],o=t[5],l=t[9],c=t[13],h=t[2],p=t[6],d=t[10],f=t[14],_=t[3],b=t[7],m=t[11],u=t[15],S=l*f-c*d,R=o*f-c*p,v=o*d-l*p,M=a*f-c*h,E=a*d-l*h,A=a*p-o*h;return e*(b*S-m*R+u*v)-n*(_*S-m*M+u*E)+s*(_*R-b*M+u*A)-r*(_*v-b*E+m*A)}determinantAffine(){let t=this.elements,e=t[0],n=t[4],s=t[8],r=t[1],a=t[5],o=t[9],l=t[2],c=t[6],h=t[10];return e*(a*h-o*c)-n*(r*h-o*l)+s*(r*c-a*l)}transpose(){let t=this.elements,e;return e=t[1],t[1]=t[4],t[4]=e,e=t[2],t[2]=t[8],t[8]=e,e=t[6],t[6]=t[9],t[9]=e,e=t[3],t[3]=t[12],t[12]=e,e=t[7],t[7]=t[13],t[13]=e,e=t[11],t[11]=t[14],t[14]=e,this}setPosition(t,e,n){let s=this.elements;return t.isVector3?(s[12]=t.x,s[13]=t.y,s[14]=t.z):(s[12]=t,s[13]=e,s[14]=n),this}invert(){let t=this.elements,e=t[0],n=t[1],s=t[2],r=t[3],a=t[4],o=t[5],l=t[6],c=t[7],h=t[8],p=t[9],d=t[10],f=t[11],_=t[12],b=t[13],m=t[14],u=t[15],S=e*o-n*a,R=e*l-s*a,v=e*c-r*a,M=n*l-s*o,E=n*c-r*o,A=s*c-r*l,g=h*b-p*_,w=h*m-d*_,T=h*u-f*_,I=p*m-d*b,N=p*u-f*b,B=d*u-f*m,F=S*B-R*N+v*I+M*T-E*w+A*g;if(F===0)return this.set(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);let P=1/F;return t[0]=(o*B-l*N+c*I)*P,t[1]=(s*N-n*B-r*I)*P,t[2]=(b*A-m*E+u*M)*P,t[3]=(d*E-p*A-f*M)*P,t[4]=(l*T-a*B-c*w)*P,t[5]=(e*B-s*T+r*w)*P,t[6]=(m*v-_*A-u*R)*P,t[7]=(h*A-d*v+f*R)*P,t[8]=(a*N-o*T+c*g)*P,t[9]=(n*T-e*N-r*g)*P,t[10]=(_*E-b*v+u*S)*P,t[11]=(p*v-h*E-f*S)*P,t[12]=(o*w-a*I-l*g)*P,t[13]=(e*I-n*w+s*g)*P,t[14]=(b*R-_*M-m*S)*P,t[15]=(h*M-p*R+d*S)*P,this}scale(t){let e=this.elements,n=t.x,s=t.y,r=t.z;return e[0]*=n,e[4]*=s,e[8]*=r,e[1]*=n,e[5]*=s,e[9]*=r,e[2]*=n,e[6]*=s,e[10]*=r,e[3]*=n,e[7]*=s,e[11]*=r,this}getMaxScaleOnAxis(){let t=this.elements,e=t[0]*t[0]+t[1]*t[1]+t[2]*t[2],n=t[4]*t[4]+t[5]*t[5]+t[6]*t[6],s=t[8]*t[8]+t[9]*t[9]+t[10]*t[10];return Math.sqrt(Math.max(e,n,s))}makeTranslation(t,e,n){return t.isVector3?this.set(1,0,0,t.x,0,1,0,t.y,0,0,1,t.z,0,0,0,1):this.set(1,0,0,t,0,1,0,e,0,0,1,n,0,0,0,1),this}makeRotationX(t){let e=Math.cos(t),n=Math.sin(t);return this.set(1,0,0,0,0,e,-n,0,0,n,e,0,0,0,0,1),this}makeRotationY(t){let e=Math.cos(t),n=Math.sin(t);return this.set(e,0,n,0,0,1,0,0,-n,0,e,0,0,0,0,1),this}makeRotationZ(t){let e=Math.cos(t),n=Math.sin(t);return this.set(e,-n,0,0,n,e,0,0,0,0,1,0,0,0,0,1),this}makeRotationAxis(t,e){let n=Math.cos(e),s=Math.sin(e),r=1-n,a=t.x,o=t.y,l=t.z,c=r*a,h=r*o;return this.set(c*a+n,c*o-s*l,c*l+s*o,0,c*o+s*l,h*o+n,h*l-s*a,0,c*l-s*o,h*l+s*a,r*l*l+n,0,0,0,0,1),this}makeScale(t,e,n){return this.set(t,0,0,0,0,e,0,0,0,0,n,0,0,0,0,1),this}makeShear(t,e,n,s,r,a){return this.set(1,n,r,0,t,1,a,0,e,s,1,0,0,0,0,1),this}compose(t,e,n){let s=this.elements,r=e._x,a=e._y,o=e._z,l=e._w,c=r+r,h=a+a,p=o+o,d=r*c,f=r*h,_=r*p,b=a*h,m=a*p,u=o*p,S=l*c,R=l*h,v=l*p,M=n.x,E=n.y,A=n.z;return s[0]=(1-(b+u))*M,s[1]=(f+v)*M,s[2]=(_-R)*M,s[3]=0,s[4]=(f-v)*E,s[5]=(1-(d+u))*E,s[6]=(m+S)*E,s[7]=0,s[8]=(_+R)*A,s[9]=(m-S)*A,s[10]=(1-(d+b))*A,s[11]=0,s[12]=t.x,s[13]=t.y,s[14]=t.z,s[15]=1,this}decompose(t,e,n){let s=this.elements;t.x=s[12],t.y=s[13],t.z=s[14];let r=this.determinantAffine();if(r===0)return n.set(1,1,1),e.identity(),this;let a=js.set(s[0],s[1],s[2]).length(),o=js.set(s[4],s[5],s[6]).length(),l=js.set(s[8],s[9],s[10]).length();r<0&&(a=-a),Qn.copy(this);let c=1/a,h=1/o,p=1/l;return Qn.elements[0]*=c,Qn.elements[1]*=c,Qn.elements[2]*=c,Qn.elements[4]*=h,Qn.elements[5]*=h,Qn.elements[6]*=h,Qn.elements[8]*=p,Qn.elements[9]*=p,Qn.elements[10]*=p,e.setFromRotationMatrix(Qn),n.x=a,n.y=o,n.z=l,this}makePerspective(t,e,n,s,r,a,o=ni,l=!1){let c=this.elements,h=2*r/(e-t),p=2*r/(n-s),d=(e+t)/(e-t),f=(n+s)/(n-s),_,b;if(l)_=r/(a-r),b=a*r/(a-r);else if(o===ni)_=-(a+r)/(a-r),b=-2*a*r/(a-r);else if(o===pr)_=-a/(a-r),b=-a*r/(a-r);else throw new Error("THREE.Matrix4.makePerspective(): Invalid coordinate system: "+o);return c[0]=h,c[4]=0,c[8]=d,c[12]=0,c[1]=0,c[5]=p,c[9]=f,c[13]=0,c[2]=0,c[6]=0,c[10]=_,c[14]=b,c[3]=0,c[7]=0,c[11]=-1,c[15]=0,this}makeOrthographic(t,e,n,s,r,a,o=ni,l=!1){let c=this.elements,h=2/(e-t),p=2/(n-s),d=-(e+t)/(e-t),f=-(n+s)/(n-s),_,b;if(l)_=1/(a-r),b=a/(a-r);else if(o===ni)_=-2/(a-r),b=-(a+r)/(a-r);else if(o===pr)_=-1/(a-r),b=-r/(a-r);else throw new Error("THREE.Matrix4.makeOrthographic(): Invalid coordinate system: "+o);return c[0]=h,c[4]=0,c[8]=0,c[12]=d,c[1]=0,c[5]=p,c[9]=0,c[13]=f,c[2]=0,c[6]=0,c[10]=_,c[14]=b,c[3]=0,c[7]=0,c[11]=0,c[15]=1,this}equals(t){let e=this.elements,n=t.elements;for(let s=0;s<16;s++)if(e[s]!==n[s])return!1;return!0}fromArray(t,e=0){for(let n=0;n<16;n++)this.elements[n]=t[n+e];return this}toArray(t=[],e=0){let n=this.elements;return t[e]=n[0],t[e+1]=n[1],t[e+2]=n[2],t[e+3]=n[3],t[e+4]=n[4],t[e+5]=n[5],t[e+6]=n[6],t[e+7]=n[7],t[e+8]=n[8],t[e+9]=n[9],t[e+10]=n[10],t[e+11]=n[11],t[e+12]=n[12],t[e+13]=n[13],t[e+14]=n[14],t[e+15]=n[15],t}};Oo.prototype.isMatrix4=!0;var be=Oo,js=new O,Qn=new be,Nf=new O(0,0,0),Uf=new O(1,1,1),ts=new O,ka=new O,In=new O,Xh=new be,qh=new Xe,zn=class i{constructor(t=0,e=0,n=0,s=i.DEFAULT_ORDER){this.isEuler=!0,this._x=t,this._y=e,this._z=n,this._order=s}get x(){return this._x}set x(t){this._x=t,this._onChangeCallback()}get y(){return this._y}set y(t){this._y=t,this._onChangeCallback()}get z(){return this._z}set z(t){this._z=t,this._onChangeCallback()}get order(){return this._order}set order(t){this._order=t,this._onChangeCallback()}set(t,e,n,s=this._order){return this._x=t,this._y=e,this._z=n,this._order=s,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._order)}copy(t){return this._x=t._x,this._y=t._y,this._z=t._z,this._order=t._order,this._onChangeCallback(),this}setFromRotationMatrix(t,e=this._order,n=!0){let s=t.elements,r=s[0],a=s[4],o=s[8],l=s[1],c=s[5],h=s[9],p=s[2],d=s[6],f=s[10];switch(e){case"XYZ":this._y=Math.asin(he(o,-1,1)),Math.abs(o)<.9999999?(this._x=Math.atan2(-h,f),this._z=Math.atan2(-a,r)):(this._x=Math.atan2(d,c),this._z=0);break;case"YXZ":this._x=Math.asin(-he(h,-1,1)),Math.abs(h)<.9999999?(this._y=Math.atan2(o,f),this._z=Math.atan2(l,c)):(this._y=Math.atan2(-p,r),this._z=0);break;case"ZXY":this._x=Math.asin(he(d,-1,1)),Math.abs(d)<.9999999?(this._y=Math.atan2(-p,f),this._z=Math.atan2(-a,c)):(this._y=0,this._z=Math.atan2(l,r));break;case"ZYX":this._y=Math.asin(-he(p,-1,1)),Math.abs(p)<.9999999?(this._x=Math.atan2(d,f),this._z=Math.atan2(l,r)):(this._x=0,this._z=Math.atan2(-a,c));break;case"YZX":this._z=Math.asin(he(l,-1,1)),Math.abs(l)<.9999999?(this._x=Math.atan2(-h,c),this._y=Math.atan2(-p,r)):(this._x=0,this._y=Math.atan2(o,f));break;case"XZY":this._z=Math.asin(-he(a,-1,1)),Math.abs(a)<.9999999?(this._x=Math.atan2(d,c),this._y=Math.atan2(o,r)):(this._x=Math.atan2(-h,f),this._y=0);break;default:Zt("Euler: .setFromRotationMatrix() encountered an unknown order: "+e)}return this._order=e,n===!0&&this._onChangeCallback(),this}setFromQuaternion(t,e,n){return Xh.makeRotationFromQuaternion(t),this.setFromRotationMatrix(Xh,e,n)}setFromVector3(t,e=this._order){return this.set(t.x,t.y,t.z,e)}reorder(t){return qh.setFromEuler(this),this.setFromQuaternion(qh,t)}equals(t){return t._x===this._x&&t._y===this._y&&t._z===this._z&&t._order===this._order}fromArray(t){return this._x=t[0],this._y=t[1],this._z=t[2],t[3]!==void 0&&(this._order=t[3]),this._onChangeCallback(),this}toArray(t=[],e=0){return t[e]=this._x,t[e+1]=this._y,t[e+2]=this._z,t[e+3]=this._order,t}_onChange(t){return this._onChangeCallback=t,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._order}};zn.DEFAULT_ORDER="XYZ";var _r=class{constructor(){this.mask=1}set(t){this.mask=(1<<t|0)>>>0}enable(t){this.mask|=1<<t|0}enableAll(){this.mask=-1}toggle(t){this.mask^=1<<t|0}disable(t){this.mask&=~(1<<t|0)}disableAll(){this.mask=0}test(t){return(this.mask&t.mask)!==0}isEnabled(t){return(this.mask&(1<<t|0))!==0}},Ff=0,Yh=new O,Qs=new Xe,zi=new be,Ha=new O,Zr=new O,Of=new O,Bf=new Xe,Zh=new O(1,0,0),$h=new O(0,1,0),Kh=new O(0,0,1),Jh={type:"added"},kf={type:"removed"},tr={type:"childadded",child:null},ec={type:"childremoved",child:null},dn=class i extends ii{constructor(){super(),this.isObject3D=!0,Object.defineProperty(this,"id",{value:Ff++}),this.uuid=Cr(),this.name="",this.type="Object3D",this.parent=null,this.children=[],this.up=i.DEFAULT_UP.clone();let t=new O,e=new zn,n=new Xe,s=new O(1,1,1);function r(){n.setFromEuler(e,!1)}function a(){e.setFromQuaternion(n,void 0,!1)}e._onChange(r),n._onChange(a),Object.defineProperties(this,{position:{configurable:!0,enumerable:!0,value:t},rotation:{configurable:!0,enumerable:!0,value:e},quaternion:{configurable:!0,enumerable:!0,value:n},scale:{configurable:!0,enumerable:!0,value:s},modelViewMatrix:{value:new be},normalMatrix:{value:new ee}}),this.matrix=new be,this.matrixWorld=new be,this.matrixAutoUpdate=i.DEFAULT_MATRIX_AUTO_UPDATE,this.matrixWorldAutoUpdate=i.DEFAULT_MATRIX_WORLD_AUTO_UPDATE,this.matrixWorldNeedsUpdate=!1,this.layers=new _r,this.visible=!0,this.castShadow=!1,this.receiveShadow=!1,this.frustumCulled=!0,this.renderOrder=0,this.animations=[],this.customDepthMaterial=void 0,this.customDistanceMaterial=void 0,this.static=!1,this.userData={},this.pivot=null}onBeforeShadow(){}onAfterShadow(){}onBeforeRender(){}onAfterRender(){}applyMatrix4(t){this.matrixAutoUpdate&&this.updateMatrix(),this.matrix.premultiply(t),this.matrix.decompose(this.position,this.quaternion,this.scale)}applyQuaternion(t){return this.quaternion.premultiply(t),this}setRotationFromAxisAngle(t,e){this.quaternion.setFromAxisAngle(t,e)}setRotationFromEuler(t){this.quaternion.setFromEuler(t,!0)}setRotationFromMatrix(t){this.quaternion.setFromRotationMatrix(t)}setRotationFromQuaternion(t){this.quaternion.copy(t)}rotateOnAxis(t,e){return Qs.setFromAxisAngle(t,e),this.quaternion.multiply(Qs),this}rotateOnWorldAxis(t,e){return Qs.setFromAxisAngle(t,e),this.quaternion.premultiply(Qs),this}rotateX(t){return this.rotateOnAxis(Zh,t)}rotateY(t){return this.rotateOnAxis($h,t)}rotateZ(t){return this.rotateOnAxis(Kh,t)}translateOnAxis(t,e){return Yh.copy(t).applyQuaternion(this.quaternion),this.position.add(Yh.multiplyScalar(e)),this}translateX(t){return this.translateOnAxis(Zh,t)}translateY(t){return this.translateOnAxis($h,t)}translateZ(t){return this.translateOnAxis(Kh,t)}localToWorld(t){return this.updateWorldMatrix(!0,!1),t.applyMatrix4(this.matrixWorld)}worldToLocal(t){return this.updateWorldMatrix(!0,!1),t.applyMatrix4(zi.copy(this.matrixWorld).invert())}lookAt(t,e,n){t.isVector3?Ha.copy(t):Ha.set(t,e,n);let s=this.parent;this.updateWorldMatrix(!0,!1),Zr.setFromMatrixPosition(this.matrixWorld),this.isCamera||this.isLight?zi.lookAt(Zr,Ha,this.up):zi.lookAt(Ha,Zr,this.up),this.quaternion.setFromRotationMatrix(zi),s&&(zi.extractRotation(s.matrixWorld),Qs.setFromRotationMatrix(zi),this.quaternion.premultiply(Qs.invert()))}add(t){if(arguments.length>1){for(let e=0;e<arguments.length;e++)this.add(arguments[e]);return this}return t===this?($t("Object3D.add: object can't be added as a child of itself.",t),this):(t&&t.isObject3D?(t.removeFromParent(),t.parent=this,this.children.push(t),t.dispatchEvent(Jh),tr.child=t,this.dispatchEvent(tr),tr.child=null):$t("Object3D.add: object not an instance of THREE.Object3D.",t),this)}remove(t){if(arguments.length>1){for(let n=0;n<arguments.length;n++)this.remove(arguments[n]);return this}let e=this.children.indexOf(t);return e!==-1&&(t.parent=null,this.children.splice(e,1),t.dispatchEvent(kf),ec.child=t,this.dispatchEvent(ec),ec.child=null),this}removeFromParent(){let t=this.parent;return t!==null&&t.remove(this),this}clear(){return this.remove(...this.children)}attach(t){return this.updateWorldMatrix(!0,!1),zi.copy(this.matrixWorld).invert(),t.parent!==null&&(t.parent.updateWorldMatrix(!0,!1),zi.multiply(t.parent.matrixWorld)),t.applyMatrix4(zi),t.removeFromParent(),t.parent=this,this.children.push(t),t.updateWorldMatrix(!1,!0),t.dispatchEvent(Jh),tr.child=t,this.dispatchEvent(tr),tr.child=null,this}getObjectById(t){return this.getObjectByProperty("id",t)}getObjectByName(t){return this.getObjectByProperty("name",t)}getObjectByProperty(t,e){if(this[t]===e)return this;for(let n=0,s=this.children.length;n<s;n++){let a=this.children[n].getObjectByProperty(t,e);if(a!==void 0)return a}}getObjectsByProperty(t,e,n=[]){this[t]===e&&n.push(this);let s=this.children;for(let r=0,a=s.length;r<a;r++)s[r].getObjectsByProperty(t,e,n);return n}getWorldPosition(t){return this.updateWorldMatrix(!0,!1),t.setFromMatrixPosition(this.matrixWorld)}getWorldQuaternion(t){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(Zr,t,Of),t}getWorldScale(t){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(Zr,Bf,t),t}getWorldDirection(t){this.updateWorldMatrix(!0,!1);let e=this.matrixWorld.elements;return t.set(e[8],e[9],e[10]).normalize()}raycast(){}intersectsFrustum(){}traverse(t){t(this);let e=this.children;for(let n=0,s=e.length;n<s;n++)e[n].traverse(t)}traverseVisible(t){if(this.visible===!1)return;t(this);let e=this.children;for(let n=0,s=e.length;n<s;n++)e[n].traverseVisible(t)}traverseAncestors(t){let e=this.parent;e!==null&&(t(e),e.traverseAncestors(t))}updateMatrix(){this.matrix.compose(this.position,this.quaternion,this.scale);let t=this.pivot;if(t!==null){let e=t.x,n=t.y,s=t.z,r=this.matrix.elements;r[12]+=e-r[0]*e-r[4]*n-r[8]*s,r[13]+=n-r[1]*e-r[5]*n-r[9]*s,r[14]+=s-r[2]*e-r[6]*n-r[10]*s}this.matrixWorldNeedsUpdate=!0}updateMatrixWorld(t){this.matrixAutoUpdate&&this.updateMatrix(),(this.matrixWorldNeedsUpdate||t)&&(this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),this.matrixWorldNeedsUpdate=!1,t=!0);let e=this.children;for(let n=0,s=e.length;n<s;n++)e[n].updateMatrixWorld(t)}updateWorldMatrix(t,e,n=!1){let s=this.parent;if(t===!0&&s!==null&&s.updateWorldMatrix(!0,!1),this.matrixAutoUpdate&&this.updateMatrix(),(this.matrixWorldNeedsUpdate||n)&&(this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),this.matrixWorldNeedsUpdate=!1,n=!0),e===!0){let r=this.children;for(let a=0,o=r.length;a<o;a++)r[a].updateWorldMatrix(!1,!0,n)}}toJSON(t){let e=t===void 0||typeof t=="string",n={};e&&(t={geometries:{},materials:{},textures:{},images:{},shapes:{},skeletons:{},animations:{},nodes:{}},n.metadata={version:4.7,type:"Object",generator:"Object3D.toJSON"});let s={};s.uuid=this.uuid,s.type=this.type,s.name=this.name,s.castShadow=this.castShadow,s.receiveShadow=this.receiveShadow,s.visible=this.visible,s.frustumCulled=this.frustumCulled,s.renderOrder=this.renderOrder,s.static=this.static,s.matrixAutoUpdate=this.matrixAutoUpdate,Object.keys(this.userData).length>0&&(s.userData=this.userData),s.layers=this.layers.mask,s.matrix=this.matrix.toArray(),s.up=this.up.toArray(),this.pivot!==null&&(s.pivot=this.pivot.toArray()),this.morphTargetDictionary!==void 0&&(s.morphTargetDictionary=Object.assign({},this.morphTargetDictionary)),this.morphTargetInfluences!==void 0&&(s.morphTargetInfluences=this.morphTargetInfluences.slice()),this.isInstancedMesh&&(s.type="InstancedMesh",s.count=this.count,s.instanceMatrix=this.instanceMatrix.toJSON(),this.instanceColor!==null&&(s.instanceColor=this.instanceColor.toJSON())),this.isBatchedMesh&&(s.type="BatchedMesh",s.perObjectFrustumCulled=this.perObjectFrustumCulled,s.sortObjects=this.sortObjects,s.drawRanges=this._drawRanges,s.reservedRanges=this._reservedRanges,s.geometryInfo=this._geometryInfo.map(o=>({...o,boundingBox:o.boundingBox?o.boundingBox.toJSON():void 0,boundingSphere:o.boundingSphere?o.boundingSphere.toJSON():void 0})),s.instanceInfo=this._instanceInfo.map(o=>({...o})),s.availableInstanceIds=this._availableInstanceIds.slice(),s.availableGeometryIds=this._availableGeometryIds.slice(),s.nextIndexStart=this._nextIndexStart,s.nextVertexStart=this._nextVertexStart,s.geometryCount=this._geometryCount,s.maxInstanceCount=this._maxInstanceCount,s.maxVertexCount=this._maxVertexCount,s.maxIndexCount=this._maxIndexCount,s.geometryInitialized=this._geometryInitialized,s.matricesTexture=this._matricesTexture.toJSON(t),s.indirectTexture=this._indirectTexture.toJSON(t),this._colorsTexture!==null&&(s.colorsTexture=this._colorsTexture.toJSON(t)),this.boundingSphere!==null&&(s.boundingSphere=this.boundingSphere.toJSON()),this.boundingBox!==null&&(s.boundingBox=this.boundingBox.toJSON()));function r(o,l){return o[l.uuid]===void 0&&(o[l.uuid]=l.toJSON(t)),l.uuid}if(this.isScene)this.background&&(this.background.isColor?s.background=this.background.toJSON():this.background.isTexture&&(s.background=this.background.toJSON(t).uuid)),this.environment&&this.environment.isTexture&&this.environment.isRenderTargetTexture!==!0&&(s.environment=this.environment.toJSON(t).uuid);else if(this.isMesh||this.isLine||this.isPoints){s.geometry=r(t.geometries,this.geometry);let o=this.geometry.parameters;if(o!==void 0&&o.shapes!==void 0){let l=o.shapes;if(Array.isArray(l))for(let c=0,h=l.length;c<h;c++){let p=l[c];r(t.shapes,p)}else r(t.shapes,l)}}if(this.isSkinnedMesh&&(s.bindMode=this.bindMode,s.bindMatrix=this.bindMatrix.toArray(),this.skeleton!==void 0&&(r(t.skeletons,this.skeleton),s.skeleton=this.skeleton.uuid)),this.material!==void 0)if(Array.isArray(this.material)){let o=[];for(let l=0,c=this.material.length;l<c;l++)o.push(r(t.materials,this.material[l]));s.material=o}else s.material=r(t.materials,this.material);if(this.children.length>0){s.children=[];for(let o=0;o<this.children.length;o++)s.children.push(this.children[o].toJSON(t).object)}if(this.animations.length>0){s.animations=[];for(let o=0;o<this.animations.length;o++){let l=this.animations[o];s.animations.push(r(t.animations,l))}}if(e){let o=a(t.geometries),l=a(t.materials),c=a(t.textures),h=a(t.images),p=a(t.shapes),d=a(t.skeletons),f=a(t.animations),_=a(t.nodes);o.length>0&&(n.geometries=o),l.length>0&&(n.materials=l),c.length>0&&(n.textures=c),h.length>0&&(n.images=h),p.length>0&&(n.shapes=p),d.length>0&&(n.skeletons=d),f.length>0&&(n.animations=f),_.length>0&&(n.nodes=_)}return n.object=s,n;function a(o){let l=[];for(let c in o){let h=o[c];delete h.metadata,l.push(h)}return l}}clone(t){return new this.constructor().copy(this,t)}copy(t,e=!0){if(this.name=t.name,this.up.copy(t.up),this.position.copy(t.position),this.rotation.order=t.rotation.order,this.quaternion.copy(t.quaternion),this.scale.copy(t.scale),this.pivot=t.pivot!==null?t.pivot.clone():null,this.matrix.copy(t.matrix),this.matrixWorld.copy(t.matrixWorld),this.matrixAutoUpdate=t.matrixAutoUpdate,this.matrixWorldAutoUpdate=t.matrixWorldAutoUpdate,this.matrixWorldNeedsUpdate=t.matrixWorldNeedsUpdate,this.layers.mask=t.layers.mask,this.visible=t.visible,this.castShadow=t.castShadow,this.receiveShadow=t.receiveShadow,this.frustumCulled=t.frustumCulled,this.renderOrder=t.renderOrder,this.static=t.static,this.animations=t.animations.slice(),this.userData=JSON.parse(JSON.stringify(t.userData)),e===!0)for(let n=0;n<t.children.length;n++){let s=t.children[n];this.add(s.clone())}return this}dispose(){this.dispatchEvent({type:"dispose"})}};dn.DEFAULT_UP=new O(0,1,0);dn.DEFAULT_MATRIX_AUTO_UPDATE=!0;dn.DEFAULT_MATRIX_WORLD_AUTO_UPDATE=!0;var ae=class extends dn{constructor(){super(),this.isGroup=!0,this.type="Group"}},Hf={type:"move"},yr=class{constructor(){this._targetRay=null,this._grip=null,this._hand=null}getHandSpace(){return this._hand===null&&(this._hand=new ae,this._hand.matrixAutoUpdate=!1,this._hand.visible=!1,this._hand.joints={},this._hand.inputState={pinching:!1}),this._hand}getTargetRaySpace(){return this._targetRay===null&&(this._targetRay=new ae,this._targetRay.matrixAutoUpdate=!1,this._targetRay.visible=!1,this._targetRay.hasLinearVelocity=!1,this._targetRay.linearVelocity=new O,this._targetRay.hasAngularVelocity=!1,this._targetRay.angularVelocity=new O),this._targetRay}getGripSpace(){return this._grip===null&&(this._grip=new ae,this._grip.matrixAutoUpdate=!1,this._grip.visible=!1,this._grip.hasLinearVelocity=!1,this._grip.linearVelocity=new O,this._grip.hasAngularVelocity=!1,this._grip.angularVelocity=new O,this._grip.eventsEnabled=!1),this._grip}dispatchEvent(t){return this._targetRay!==null&&this._targetRay.dispatchEvent(t),this._grip!==null&&this._grip.dispatchEvent(t),this._hand!==null&&this._hand.dispatchEvent(t),this}connect(t){if(t&&t.hand){let e=this._hand;if(e)for(let n of t.hand.values())this._getHandJoint(e,n)}return this.dispatchEvent({type:"connected",data:t}),this}disconnect(t){return this.dispatchEvent({type:"disconnected",data:t}),this._targetRay!==null&&(this._targetRay.visible=!1),this._grip!==null&&(this._grip.visible=!1),this._hand!==null&&(this._hand.visible=!1),this}update(t,e,n){let s=null,r=null,a=null,o=this._targetRay,l=this._grip,c=this._hand;if(t&&e.session.visibilityState!=="visible-blurred"){if(c&&t.hand){a=!0;for(let b of t.hand.values()){let m=e.getJointPose(b,n),u=this._getHandJoint(c,b);m!==null&&(u.matrix.fromArray(m.transform.matrix),u.matrix.decompose(u.position,u.rotation,u.scale),u.matrixWorldNeedsUpdate=!0,u.jointRadius=m.radius),u.visible=m!==null}let h=c.joints["index-finger-tip"],p=c.joints["thumb-tip"],d=h.position.distanceTo(p.position),f=.02,_=.005;c.inputState.pinching&&d>f+_?(c.inputState.pinching=!1,this.dispatchEvent({type:"pinchend",handedness:t.handedness,target:this})):!c.inputState.pinching&&d<=f-_&&(c.inputState.pinching=!0,this.dispatchEvent({type:"pinchstart",handedness:t.handedness,target:this}))}else l!==null&&t.gripSpace&&(r=e.getPose(t.gripSpace,n),r!==null&&(l.matrix.fromArray(r.transform.matrix),l.matrix.decompose(l.position,l.rotation,l.scale),l.matrixWorldNeedsUpdate=!0,r.linearVelocity?(l.hasLinearVelocity=!0,l.linearVelocity.copy(r.linearVelocity)):l.hasLinearVelocity=!1,r.angularVelocity?(l.hasAngularVelocity=!0,l.angularVelocity.copy(r.angularVelocity)):l.hasAngularVelocity=!1,l.eventsEnabled&&l.dispatchEvent({type:"gripUpdated",data:t,target:this})));o!==null&&(s=e.getPose(t.targetRaySpace,n),s===null&&r!==null&&(s=r),s!==null&&(o.matrix.fromArray(s.transform.matrix),o.matrix.decompose(o.position,o.rotation,o.scale),o.matrixWorldNeedsUpdate=!0,s.linearVelocity?(o.hasLinearVelocity=!0,o.linearVelocity.copy(s.linearVelocity)):o.hasLinearVelocity=!1,s.angularVelocity?(o.hasAngularVelocity=!0,o.angularVelocity.copy(s.angularVelocity)):o.hasAngularVelocity=!1,this.dispatchEvent(Hf)))}return o!==null&&(o.visible=s!==null),l!==null&&(l.visible=r!==null),c!==null&&(c.visible=a!==null),this}_getHandJoint(t,e){if(t.joints[e.jointName]===void 0){let n=new ae;n.matrixAutoUpdate=!1,n.visible=!1,t.joints[e.jointName]=n,t.add(n)}return t.joints[e.jointName]}},Ku={aliceblue:15792383,antiquewhite:16444375,aqua:65535,aquamarine:8388564,azure:15794175,beige:16119260,bisque:16770244,black:0,blanchedalmond:16772045,blue:255,blueviolet:9055202,brown:10824234,burlywood:14596231,cadetblue:6266528,chartreuse:8388352,chocolate:13789470,coral:16744272,cornflowerblue:6591981,cornsilk:16775388,crimson:14423100,cyan:65535,darkblue:139,darkcyan:35723,darkgoldenrod:12092939,darkgray:11119017,darkgreen:25600,darkgrey:11119017,darkkhaki:12433259,darkmagenta:9109643,darkolivegreen:5597999,darkorange:16747520,darkorchid:10040012,darkred:9109504,darksalmon:15308410,darkseagreen:9419919,darkslateblue:4734347,darkslategray:3100495,darkslategrey:3100495,darkturquoise:52945,darkviolet:9699539,deeppink:16716947,deepskyblue:49151,dimgray:6908265,dimgrey:6908265,dodgerblue:2003199,firebrick:11674146,floralwhite:16775920,forestgreen:2263842,fuchsia:16711935,gainsboro:14474460,ghostwhite:16316671,gold:16766720,goldenrod:14329120,gray:8421504,green:32768,greenyellow:11403055,grey:8421504,honeydew:15794160,hotpink:16738740,indianred:13458524,indigo:4915330,ivory:16777200,khaki:15787660,lavender:15132410,lavenderblush:16773365,lawngreen:8190976,lemonchiffon:16775885,lightblue:11393254,lightcoral:15761536,lightcyan:14745599,lightgoldenrodyellow:16448210,lightgray:13882323,lightgreen:9498256,lightgrey:13882323,lightpink:16758465,lightsalmon:16752762,lightseagreen:2142890,lightskyblue:8900346,lightslategray:7833753,lightslategrey:7833753,lightsteelblue:11584734,lightyellow:16777184,lime:65280,limegreen:3329330,linen:16445670,magenta:16711935,maroon:8388608,mediumaquamarine:6737322,mediumblue:205,mediumorchid:12211667,mediumpurple:9662683,mediumseagreen:3978097,mediumslateblue:8087790,mediumspringgreen:64154,mediumturquoise:4772300,mediumvioletred:13047173,midnightblue:1644912,mintcream:16121850,mistyrose:16770273,moccasin:16770229,navajowhite:16768685,navy:128,oldlace:16643558,olive:8421376,olivedrab:7048739,orange:16753920,orangered:16729344,orchid:14315734,palegoldenrod:15657130,palegreen:10025880,paleturquoise:11529966,palevioletred:14381203,papayawhip:16773077,peachpuff:16767673,peru:13468991,pink:16761035,plum:14524637,powderblue:11591910,purple:8388736,rebeccapurple:6697881,red:16711680,rosybrown:12357519,royalblue:4286945,saddlebrown:9127187,salmon:16416882,sandybrown:16032864,seagreen:3050327,seashell:16774638,sienna:10506797,silver:12632256,skyblue:8900331,slateblue:6970061,slategray:7372944,slategrey:7372944,snow:16775930,springgreen:65407,steelblue:4620980,tan:13808780,teal:32896,thistle:14204888,tomato:16737095,turquoise:4251856,violet:15631086,wheat:16113331,white:16777215,whitesmoke:16119285,yellow:16776960,yellowgreen:10145074},es={h:0,s:0,l:0},Va={h:0,s:0,l:0};function nc(i,t,e){return e<0&&(e+=1),e>1&&(e-=1),e<1/6?i+(t-i)*6*e:e<1/2?t:e<2/3?i+(t-i)*6*(2/3-e):i}var jt=class{constructor(t,e,n){return this.isColor=!0,this.r=1,this.g=1,this.b=1,this.set(t,e,n)}set(t,e,n){if(e===void 0&&n===void 0){let s=t;s&&s.isColor?this.copy(s):typeof s=="number"?this.setHex(s):typeof s=="string"&&this.setStyle(s)}else this.setRGB(t,e,n);return this}setScalar(t){return this.r=t,this.g=t,this.b=t,this}setHex(t,e=He){return t=Math.floor(t),this.r=(t>>16&255)/255,this.g=(t>>8&255)/255,this.b=(t&255)/255,me.colorSpaceToWorking(this,e),this}setRGB(t,e,n,s=me.workingColorSpace){return this.r=t,this.g=e,this.b=n,me.colorSpaceToWorking(this,s),this}setHSL(t,e,n,s=me.workingColorSpace){if(t=$c(t,1),e=he(e,0,1),n=he(n,0,1),e===0)this.r=this.g=this.b=n;else{let r=n<=.5?n*(1+e):n+e-n*e,a=2*n-r;this.r=nc(a,r,t+1/3),this.g=nc(a,r,t),this.b=nc(a,r,t-1/3)}return me.colorSpaceToWorking(this,s),this}setStyle(t,e=He){function n(r){r!==void 0&&parseFloat(r)<1&&Zt("Color: Alpha component of "+t+" will be ignored.")}let s;if(s=/^(\w+)\(([^\)]*)\)/.exec(t)){let r,a=s[1],o=s[2];switch(a){case"rgb":case"rgba":if(r=/^\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(o))return n(r[4]),this.setRGB(Math.min(255,parseInt(r[1],10))/255,Math.min(255,parseInt(r[2],10))/255,Math.min(255,parseInt(r[3],10))/255,e);if(r=/^\s*(\d+)\%\s*,\s*(\d+)\%\s*,\s*(\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(o))return n(r[4]),this.setRGB(Math.min(100,parseInt(r[1],10))/100,Math.min(100,parseInt(r[2],10))/100,Math.min(100,parseInt(r[3],10))/100,e);break;case"hsl":case"hsla":if(r=/^\s*(\d*\.?\d+)\s*,\s*(\d*\.?\d+)\%\s*,\s*(\d*\.?\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(o))return n(r[4]),this.setHSL(parseFloat(r[1])/360,parseFloat(r[2])/100,parseFloat(r[3])/100,e);break;default:Zt("Color: Unknown color model "+t)}}else if(s=/^\#([A-Fa-f\d]+)$/.exec(t)){let r=s[1],a=r.length;if(a===3)return this.setRGB(parseInt(r.charAt(0),16)/15,parseInt(r.charAt(1),16)/15,parseInt(r.charAt(2),16)/15,e);if(a===6)return this.setHex(parseInt(r,16),e);Zt("Color: Invalid hex color "+t)}else if(t&&t.length>0)return this.setColorName(t,e);return this}setColorName(t,e=He){let n=Ku[t.toLowerCase()];return n!==void 0?this.setHex(n,e):Zt("Color: Unknown color "+t),this}clone(){return new this.constructor(this.r,this.g,this.b)}copy(t){return this.r=t.r,this.g=t.g,this.b=t.b,this}copySRGBToLinear(t){return this.r=Bi(t.r),this.g=Bi(t.g),this.b=Bi(t.b),this}copyLinearToSRGB(t){return this.r=dr(t.r),this.g=dr(t.g),this.b=dr(t.b),this}convertSRGBToLinear(){return this.copySRGBToLinear(this),this}convertLinearToSRGB(){return this.copyLinearToSRGB(this),this}getHex(t=He){return me.workingToColorSpace(un.copy(this),t),Math.round(he(un.r*255,0,255))*65536+Math.round(he(un.g*255,0,255))*256+Math.round(he(un.b*255,0,255))}getHexString(t=He){return("000000"+this.getHex(t).toString(16)).slice(-6)}getHSL(t,e=me.workingColorSpace){me.workingToColorSpace(un.copy(this),e);let n=un.r,s=un.g,r=un.b,a=Math.max(n,s,r),o=Math.min(n,s,r),l,c,h=(o+a)/2;if(o===a)l=0,c=0;else{let p=a-o;switch(c=h<=.5?p/(a+o):p/(2-a-o),a){case n:l=(s-r)/p+(s<r?6:0);break;case s:l=(r-n)/p+2;break;case r:l=(n-s)/p+4;break}l/=6}return t.h=l,t.s=c,t.l=h,t}getRGB(t,e=me.workingColorSpace){return me.workingToColorSpace(un.copy(this),e),t.r=un.r,t.g=un.g,t.b=un.b,t}getStyle(t=He){me.workingToColorSpace(un.copy(this),t);let e=un.r,n=un.g,s=un.b;return t!==He?`color(${t} ${e.toFixed(3)} ${n.toFixed(3)} ${s.toFixed(3)})`:`rgb(${Math.round(e*255)},${Math.round(n*255)},${Math.round(s*255)})`}offsetHSL(t,e,n){return this.getHSL(es),this.setHSL(es.h+t,es.s+e,es.l+n)}add(t){return this.r+=t.r,this.g+=t.g,this.b+=t.b,this}addColors(t,e){return this.r=t.r+e.r,this.g=t.g+e.g,this.b=t.b+e.b,this}addScalar(t){return this.r+=t,this.g+=t,this.b+=t,this}sub(t){return this.r=Math.max(0,this.r-t.r),this.g=Math.max(0,this.g-t.g),this.b=Math.max(0,this.b-t.b),this}multiply(t){return this.r*=t.r,this.g*=t.g,this.b*=t.b,this}multiplyScalar(t){return this.r*=t,this.g*=t,this.b*=t,this}lerp(t,e){return this.r+=(t.r-this.r)*e,this.g+=(t.g-this.g)*e,this.b+=(t.b-this.b)*e,this}lerpColors(t,e,n){return this.r=t.r+(e.r-t.r)*n,this.g=t.g+(e.g-t.g)*n,this.b=t.b+(e.b-t.b)*n,this}lerpHSL(t,e){this.getHSL(es),t.getHSL(Va);let n=ea(es.h,Va.h,e),s=ea(es.s,Va.s,e),r=ea(es.l,Va.l,e);return this.setHSL(n,s,r),this}setFromVector3(t){return this.r=t.x,this.g=t.y,this.b=t.z,this}applyMatrix3(t){let e=this.r,n=this.g,s=this.b,r=t.elements;return this.r=r[0]*e+r[3]*n+r[6]*s,this.g=r[1]*e+r[4]*n+r[7]*s,this.b=r[2]*e+r[5]*n+r[8]*s,this}equals(t){return t.r===this.r&&t.g===this.g&&t.b===this.b}fromArray(t,e=0){return this.r=t[e],this.g=t[e+1],this.b=t[e+2],this}toArray(t=[],e=0){return t[e]=this.r,t[e+1]=this.g,t[e+2]=this.b,t}fromBufferAttribute(t,e){return this.r=t.getX(e),this.g=t.getY(e),this.b=t.getZ(e),this}toJSON(){return this.getHex()}*[Symbol.iterator](){yield this.r,yield this.g,yield this.b}},un=new jt;jt.NAMES=Ku;var Ds=class extends dn{constructor(){super(),this.isScene=!0,this.type="Scene",this.background=null,this.environment=null,this.fog=null,this.backgroundBlurriness=0,this.backgroundIntensity=1,this.backgroundRotation=new zn,this.environmentIntensity=1,this.environmentRotation=new zn,this.overrideMaterial=null,typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}copy(t,e){return super.copy(t,e),t.background!==null&&(this.background=t.background.clone()),t.environment!==null&&(this.environment=t.environment.clone()),t.fog!==null&&(this.fog=t.fog.clone()),this.backgroundBlurriness=t.backgroundBlurriness,this.backgroundIntensity=t.backgroundIntensity,this.backgroundRotation.copy(t.backgroundRotation),this.environmentIntensity=t.environmentIntensity,this.environmentRotation.copy(t.environmentRotation),t.overrideMaterial!==null&&(this.overrideMaterial=t.overrideMaterial.clone()),this.matrixAutoUpdate=t.matrixAutoUpdate,this}toJSON(t){let e=super.toJSON(t);return this.fog!==null&&(e.object.fog=this.fog.toJSON()),e.object.backgroundBlurriness=this.backgroundBlurriness,e.object.backgroundIntensity=this.backgroundIntensity,e.object.backgroundRotation=this.backgroundRotation.toArray(),e.object.environmentIntensity=this.environmentIntensity,e.object.environmentRotation=this.environmentRotation.toArray(),e}},ti=new O,Ni=new O,ic=new O,Ui=new O,er=new O,nr=new O,jh=new O,sc=new O,rc=new O,ac=new O,oc=new Oe,lc=new Oe,cc=new Oe,rs=class i{constructor(t=new O,e=new O,n=new O){this.a=t,this.b=e,this.c=n}static getNormal(t,e,n,s){s.subVectors(n,e),ti.subVectors(t,e),s.cross(ti);let r=s.lengthSq();return r>0?s.multiplyScalar(1/Math.sqrt(r)):s.set(0,0,0)}static getBarycoord(t,e,n,s,r){ti.subVectors(s,e),Ni.subVectors(n,e),ic.subVectors(t,e);let a=ti.dot(ti),o=ti.dot(Ni),l=ti.dot(ic),c=Ni.dot(Ni),h=Ni.dot(ic),p=a*c-o*o;if(p===0)return r.set(0,0,0),null;let d=1/p,f=(c*l-o*h)*d,_=(a*h-o*l)*d;return r.set(1-f-_,_,f)}static containsPoint(t,e,n,s){return this.getBarycoord(t,e,n,s,Ui)===null?!1:Ui.x>=0&&Ui.y>=0&&Ui.x+Ui.y<=1}static getInterpolation(t,e,n,s,r,a,o,l){return this.getBarycoord(t,e,n,s,Ui)===null?(l.x=0,l.y=0,"z"in l&&(l.z=0),"w"in l&&(l.w=0),null):(l.setScalar(0),l.addScaledVector(r,Ui.x),l.addScaledVector(a,Ui.y),l.addScaledVector(o,Ui.z),l)}static getInterpolatedAttribute(t,e,n,s,r,a){return oc.setScalar(0),lc.setScalar(0),cc.setScalar(0),oc.fromBufferAttribute(t,e),lc.fromBufferAttribute(t,n),cc.fromBufferAttribute(t,s),a.setScalar(0),a.addScaledVector(oc,r.x),a.addScaledVector(lc,r.y),a.addScaledVector(cc,r.z),a}static isFrontFacing(t,e,n,s){return ti.subVectors(n,e),Ni.subVectors(t,e),ti.cross(Ni).dot(s)<0}set(t,e,n){return this.a.copy(t),this.b.copy(e),this.c.copy(n),this}setFromPointsAndIndices(t,e,n,s){return this.a.copy(t[e]),this.b.copy(t[n]),this.c.copy(t[s]),this}setFromAttributeAndIndices(t,e,n,s){return this.a.fromBufferAttribute(t,e),this.b.fromBufferAttribute(t,n),this.c.fromBufferAttribute(t,s),this}clone(){return new this.constructor().copy(this)}copy(t){return this.a.copy(t.a),this.b.copy(t.b),this.c.copy(t.c),this}getArea(){return ti.subVectors(this.c,this.b),Ni.subVectors(this.a,this.b),ti.cross(Ni).length()*.5}getMidpoint(t){return t.addVectors(this.a,this.b).add(this.c).multiplyScalar(1/3)}getNormal(t){return i.getNormal(this.a,this.b,this.c,t)}getPlane(t){return t.setFromCoplanarPoints(this.a,this.b,this.c)}getBarycoord(t,e){return i.getBarycoord(t,this.a,this.b,this.c,e)}getInterpolation(t,e,n,s,r){return i.getInterpolation(t,this.a,this.b,this.c,e,n,s,r)}containsPoint(t){return i.containsPoint(t,this.a,this.b,this.c)}isFrontFacing(t){return i.isFrontFacing(this.a,this.b,this.c,t)}intersectsBox(t){return t.intersectsTriangle(this)}closestPointToPoint(t,e){let n=this.a,s=this.b,r=this.c,a,o;er.subVectors(s,n),nr.subVectors(r,n),sc.subVectors(t,n);let l=er.dot(sc),c=nr.dot(sc);if(l<=0&&c<=0)return e.copy(n);rc.subVectors(t,s);let h=er.dot(rc),p=nr.dot(rc);if(h>=0&&p<=h)return e.copy(s);let d=l*p-h*c;if(d<=0&&l>=0&&h<=0)return a=l/(l-h),e.copy(n).addScaledVector(er,a);ac.subVectors(t,r);let f=er.dot(ac),_=nr.dot(ac);if(_>=0&&f<=_)return e.copy(r);let b=f*c-l*_;if(b<=0&&c>=0&&_<=0)return o=c/(c-_),e.copy(n).addScaledVector(nr,o);let m=h*_-f*p;if(m<=0&&p-h>=0&&f-_>=0)return jh.subVectors(r,s),o=(p-h)/(p-h+(f-_)),e.copy(s).addScaledVector(jh,o);let u=1/(m+b+d);return a=b*u,o=d*u,e.copy(n).addScaledVector(er,a).addScaledVector(nr,o)}equals(t){return t.a.equals(this.a)&&t.b.equals(this.b)&&t.c.equals(this.c)}},_i=class{constructor(t=new O(1/0,1/0,1/0),e=new O(-1/0,-1/0,-1/0)){this.isBox3=!0,this.min=t,this.max=e}set(t,e){return this.min.copy(t),this.max.copy(e),this}setFromArray(t){this.makeEmpty();for(let e=0,n=t.length;e<n;e+=3)this.expandByPoint(ei.fromArray(t,e));return this}setFromBufferAttribute(t){this.makeEmpty();for(let e=0,n=t.count;e<n;e++)this.expandByPoint(ei.fromBufferAttribute(t,e));return this}setFromPoints(t){this.makeEmpty();for(let e=0,n=t.length;e<n;e++)this.expandByPoint(t[e]);return this}setFromCenterAndSize(t,e){let n=ei.copy(e).multiplyScalar(.5);return this.min.copy(t).sub(n),this.max.copy(t).add(n),this}setFromObject(t,e=!1){return this.makeEmpty(),this.expandByObject(t,e)}clone(){return new this.constructor().copy(this)}copy(t){return this.min.copy(t.min),this.max.copy(t.max),this}makeEmpty(){return this.min.x=this.min.y=this.min.z=1/0,this.max.x=this.max.y=this.max.z=-1/0,this}isEmpty(){return this.max.x<this.min.x||this.max.y<this.min.y||this.max.z<this.min.z}getCenter(t){return this.isEmpty()?t.set(0,0,0):t.addVectors(this.min,this.max).multiplyScalar(.5)}getSize(t){return this.isEmpty()?t.set(0,0,0):t.subVectors(this.max,this.min)}expandByPoint(t){return this.min.min(t),this.max.max(t),this}expandByVector(t){return this.min.sub(t),this.max.add(t),this}expandByScalar(t){return this.min.addScalar(-t),this.max.addScalar(t),this}expandByObject(t,e=!1){t.updateWorldMatrix(!1,!1);let n=t.geometry;if(n!==void 0){let r=n.getAttribute("position");if(e===!0&&r!==void 0&&t.isInstancedMesh!==!0)for(let a=0,o=r.count;a<o;a++)t.isMesh===!0?t.getVertexPosition(a,ei):ei.fromBufferAttribute(r,a),ei.applyMatrix4(t.matrixWorld),this.expandByPoint(ei);else t.boundingBox!==void 0?(t.boundingBox===null&&t.computeBoundingBox(),Ga.copy(t.boundingBox)):(n.boundingBox===null&&n.computeBoundingBox(),Ga.copy(n.boundingBox)),Ga.applyMatrix4(t.matrixWorld),this.union(Ga)}let s=t.children;for(let r=0,a=s.length;r<a;r++)this.expandByObject(s[r],e);return this}containsPoint(t){return t.x>=this.min.x&&t.x<=this.max.x&&t.y>=this.min.y&&t.y<=this.max.y&&t.z>=this.min.z&&t.z<=this.max.z}containsBox(t){return this.min.x<=t.min.x&&t.max.x<=this.max.x&&this.min.y<=t.min.y&&t.max.y<=this.max.y&&this.min.z<=t.min.z&&t.max.z<=this.max.z}getParameter(t,e){return e.set((t.x-this.min.x)/(this.max.x-this.min.x),(t.y-this.min.y)/(this.max.y-this.min.y),(t.z-this.min.z)/(this.max.z-this.min.z))}intersectsBox(t){return t.max.x>=this.min.x&&t.min.x<=this.max.x&&t.max.y>=this.min.y&&t.min.y<=this.max.y&&t.max.z>=this.min.z&&t.min.z<=this.max.z}intersectsSphere(t){return this.clampPoint(t.center,ei),ei.distanceToSquared(t.center)<=t.radius*t.radius}intersectsPlane(t){let e,n;return t.normal.x>0?(e=t.normal.x*this.min.x,n=t.normal.x*this.max.x):(e=t.normal.x*this.max.x,n=t.normal.x*this.min.x),t.normal.y>0?(e+=t.normal.y*this.min.y,n+=t.normal.y*this.max.y):(e+=t.normal.y*this.max.y,n+=t.normal.y*this.min.y),t.normal.z>0?(e+=t.normal.z*this.min.z,n+=t.normal.z*this.max.z):(e+=t.normal.z*this.max.z,n+=t.normal.z*this.min.z),e<=-t.constant&&n>=-t.constant}intersectsTriangle(t){if(this.isEmpty())return!1;this.getCenter($r),Wa.subVectors(this.max,$r),ir.subVectors(t.a,$r),sr.subVectors(t.b,$r),rr.subVectors(t.c,$r),ns.subVectors(sr,ir),is.subVectors(rr,sr),Rs.subVectors(ir,rr);let e=[0,-ns.z,ns.y,0,-is.z,is.y,0,-Rs.z,Rs.y,ns.z,0,-ns.x,is.z,0,-is.x,Rs.z,0,-Rs.x,-ns.y,ns.x,0,-is.y,is.x,0,-Rs.y,Rs.x,0];return!hc(e,ir,sr,rr,Wa)||(e=[1,0,0,0,1,0,0,0,1],!hc(e,ir,sr,rr,Wa))?!1:(Xa.crossVectors(ns,is),e=[Xa.x,Xa.y,Xa.z],hc(e,ir,sr,rr,Wa))}clampPoint(t,e){return e.copy(t).clamp(this.min,this.max)}distanceToPoint(t){return this.clampPoint(t,ei).distanceTo(t)}getBoundingSphere(t){return this.isEmpty()?t.makeEmpty():(this.getCenter(t.center),t.radius=this.getSize(ei).length()*.5),t}intersect(t){return this.min.max(t.min),this.max.min(t.max),this.isEmpty()&&this.makeEmpty(),this}union(t){return this.min.min(t.min),this.max.max(t.max),this}applyMatrix4(t){return this.isEmpty()?this:(Fi[0].set(this.min.x,this.min.y,this.min.z).applyMatrix4(t),Fi[1].set(this.min.x,this.min.y,this.max.z).applyMatrix4(t),Fi[2].set(this.min.x,this.max.y,this.min.z).applyMatrix4(t),Fi[3].set(this.min.x,this.max.y,this.max.z).applyMatrix4(t),Fi[4].set(this.max.x,this.min.y,this.min.z).applyMatrix4(t),Fi[5].set(this.max.x,this.min.y,this.max.z).applyMatrix4(t),Fi[6].set(this.max.x,this.max.y,this.min.z).applyMatrix4(t),Fi[7].set(this.max.x,this.max.y,this.max.z).applyMatrix4(t),this.setFromPoints(Fi),this)}translate(t){return this.min.add(t),this.max.add(t),this}equals(t){return t.min.equals(this.min)&&t.max.equals(this.max)}toJSON(){return{min:this.min.toArray(),max:this.max.toArray()}}fromJSON(t){return this.min.fromArray(t.min),this.max.fromArray(t.max),this}},Fi=[new O,new O,new O,new O,new O,new O,new O,new O],ei=new O,Ga=new _i,ir=new O,sr=new O,rr=new O,ns=new O,is=new O,Rs=new O,$r=new O,Wa=new O,Xa=new O,Cs=new O;function hc(i,t,e,n,s){for(let r=0,a=i.length-3;r<=a;r+=3){Cs.fromArray(i,r);let o=s.x*Math.abs(Cs.x)+s.y*Math.abs(Cs.y)+s.z*Math.abs(Cs.z),l=t.dot(Cs),c=e.dot(Cs),h=n.dot(Cs);if(Math.max(-Math.max(l,c,h),Math.min(l,c,h))>o)return!1}return!0}var We=new O,qa=new qt,Vf=0,on=class extends ii{constructor(t,e,n=!1){if(super(),Array.isArray(t))throw new TypeError("THREE.BufferAttribute: array should be a Typed Array.");this.isBufferAttribute=!0,Object.defineProperty(this,"id",{value:Vf++}),this.name="",this.array=t,this.itemSize=e,this.count=t!==void 0?t.length/e:0,this.normalized=n,this.usage=Xu,this.updateRanges=[],this.gpuType=Vn,this.version=0}onUploadCallback(){}set needsUpdate(t){t===!0&&this.version++}setUsage(t){return this.usage=t,this}addUpdateRange(t,e){this.updateRanges.push({start:t,count:e})}clearUpdateRanges(){this.updateRanges.length=0}copy(t){return this.name=t.name,this.array=new t.array.constructor(t.array),this.itemSize=t.itemSize,this.count=t.count,this.normalized=t.normalized,this.usage=t.usage,this.gpuType=t.gpuType,this}copyAt(t,e,n){t*=this.itemSize,n*=e.itemSize;for(let s=0,r=this.itemSize;s<r;s++)this.array[t+s]=e.array[n+s];return this}copyArray(t){return this.array.set(t),this}applyMatrix3(t){if(this.itemSize===2)for(let e=0,n=this.count;e<n;e++)qa.fromBufferAttribute(this,e),qa.applyMatrix3(t),this.setXY(e,qa.x,qa.y);else if(this.itemSize===3)for(let e=0,n=this.count;e<n;e++)We.fromBufferAttribute(this,e),We.applyMatrix3(t),this.setXYZ(e,We.x,We.y,We.z);return this}applyMatrix4(t){for(let e=0,n=this.count;e<n;e++)We.fromBufferAttribute(this,e),We.applyMatrix4(t),this.setXYZ(e,We.x,We.y,We.z);return this}applyNormalMatrix(t){for(let e=0,n=this.count;e<n;e++)We.fromBufferAttribute(this,e),We.applyNormalMatrix(t),this.setXYZ(e,We.x,We.y,We.z);return this}transformDirection(t){for(let e=0,n=this.count;e<n;e++)We.fromBufferAttribute(this,e),We.transformDirection(t),this.setXYZ(e,We.x,We.y,We.z);return this}set(t,e=0){return this.array.set(t,e),this}getComponent(t,e){let n=this.array[t*this.itemSize+e];return this.normalized&&(n=ur(n,this.array)),n}setComponent(t,e,n){return this.normalized&&(n=yn(n,this.array)),this.array[t*this.itemSize+e]=n,this}getX(t){let e=this.array[t*this.itemSize];return this.normalized&&(e=ur(e,this.array)),e}setX(t,e){return this.normalized&&(e=yn(e,this.array)),this.array[t*this.itemSize]=e,this}getY(t){let e=this.array[t*this.itemSize+1];return this.normalized&&(e=ur(e,this.array)),e}setY(t,e){return this.normalized&&(e=yn(e,this.array)),this.array[t*this.itemSize+1]=e,this}getZ(t){let e=this.array[t*this.itemSize+2];return this.normalized&&(e=ur(e,this.array)),e}setZ(t,e){return this.normalized&&(e=yn(e,this.array)),this.array[t*this.itemSize+2]=e,this}getW(t){let e=this.array[t*this.itemSize+3];return this.normalized&&(e=ur(e,this.array)),e}setW(t,e){return this.normalized&&(e=yn(e,this.array)),this.array[t*this.itemSize+3]=e,this}setXY(t,e,n){return t*=this.itemSize,this.normalized&&(e=yn(e,this.array),n=yn(n,this.array)),this.array[t+0]=e,this.array[t+1]=n,this}setXYZ(t,e,n,s){return t*=this.itemSize,this.normalized&&(e=yn(e,this.array),n=yn(n,this.array),s=yn(s,this.array)),this.array[t+0]=e,this.array[t+1]=n,this.array[t+2]=s,this}setXYZW(t,e,n,s,r){return t*=this.itemSize,this.normalized&&(e=yn(e,this.array),n=yn(n,this.array),s=yn(s,this.array),r=yn(r,this.array)),this.array[t+0]=e,this.array[t+1]=n,this.array[t+2]=s,this.array[t+3]=r,this}onUpload(t){return this.onUploadCallback=t,this}clone(){return new this.constructor(this.array,this.itemSize).copy(this)}toJSON(){let t={itemSize:this.itemSize,type:this.array.constructor.name,array:Array.from(this.array),normalized:this.normalized};return t.name=this.name,t.usage=this.usage,t.gpuType=this.gpuType,t}dispose(){this.dispatchEvent({type:"dispose"})}};var oa=class extends on{constructor(t,e,n){super(new Uint16Array(t),e,n)}};var la=class extends on{constructor(t,e,n){super(new Uint32Array(t),e,n)}};var Fe=class extends on{constructor(t,e,n){super(new Float32Array(t),e,n)}},Gf=new _i,Kr=new O,uc=new O,as=class{constructor(t=new O,e=-1){this.isSphere=!0,this.center=t,this.radius=e}set(t,e){return this.center.copy(t),this.radius=e,this}setFromPoints(t,e){let n=this.center;e!==void 0?n.copy(e):Gf.setFromPoints(t).getCenter(n);let s=0;for(let r=0,a=t.length;r<a;r++)s=Math.max(s,n.distanceToSquared(t[r]));return this.radius=Math.sqrt(s),this}copy(t){return this.center.copy(t.center),this.radius=t.radius,this}isEmpty(){return this.radius<0}makeEmpty(){return this.center.set(0,0,0),this.radius=-1,this}containsPoint(t){return t.distanceToSquared(this.center)<=this.radius*this.radius}distanceToPoint(t){return t.distanceTo(this.center)-this.radius}intersectsSphere(t){let e=this.radius+t.radius;return t.center.distanceToSquared(this.center)<=e*e}intersectsBox(t){return t.intersectsSphere(this)}intersectsPlane(t){return Math.abs(t.distanceToPoint(this.center))<=this.radius}clampPoint(t,e){let n=this.center.distanceToSquared(t);return e.copy(t),n>this.radius*this.radius&&(e.sub(this.center).normalize(),e.multiplyScalar(this.radius).add(this.center)),e}getBoundingBox(t){return this.isEmpty()?(t.makeEmpty(),t):(t.set(this.center,this.center),t.expandByScalar(this.radius),t)}applyMatrix4(t){return this.center.applyMatrix4(t),this.radius=this.radius*t.getMaxScaleOnAxis(),this}translate(t){return this.center.add(t),this}expandByPoint(t){if(this.isEmpty())return this.center.copy(t),this.radius=0,this;Kr.subVectors(t,this.center);let e=Kr.lengthSq();if(e>this.radius*this.radius){let n=Math.sqrt(e),s=(n-this.radius)*.5;this.center.addScaledVector(Kr,s/n),this.radius+=s}return this}union(t){return t.isEmpty()?this:this.isEmpty()?(this.copy(t),this):(this.center.equals(t.center)===!0?this.radius=Math.max(this.radius,t.radius):(uc.subVectors(t.center,this.center).setLength(t.radius),this.expandByPoint(Kr.copy(t.center).add(uc)),this.expandByPoint(Kr.copy(t.center).sub(uc))),this)}equals(t){return t.center.equals(this.center)&&t.radius===this.radius}clone(){return new this.constructor().copy(this)}toJSON(){return{radius:this.radius,center:this.center.toArray()}}fromJSON(t){return this.radius=t.radius,this.center.fromArray(t.center),this}},Wf=0,Hn=new be,dc=new dn,ar=new O,Ln=new _i,Jr=new _i,Qe=new O,fn=class i extends ii{constructor(){super(),this.isBufferGeometry=!0,Object.defineProperty(this,"id",{value:Wf++}),this.uuid=Cr(),this.name="",this.type="BufferGeometry",this.index=null,this.indirect=null,this.indirectOffset=0,this.attributes={},this.morphAttributes={},this.morphTargetsRelative=!1,this.groups=[],this.boundingBox=null,this.boundingSphere=null,this.drawRange={start:0,count:1/0},this.userData={},this._transformed=!1}getIndex(){return this.index}setIndex(t){return Array.isArray(t)?this.index=new(pf(t)?la:oa)(t,1):this.index=t,this}setIndirect(t,e=0){return this.indirect=t,this.indirectOffset=e,this}getIndirect(){return this.indirect}getAttribute(t){return this.attributes[t]}setAttribute(t,e){return this.attributes[t]=e,this}deleteAttribute(t){return delete this.attributes[t],this}hasAttribute(t){return this.attributes[t]!==void 0}addGroup(t,e,n=0){this.groups.push({start:t,count:e,materialIndex:n})}clearGroups(){this.groups=[]}setDrawRange(t,e){this.drawRange.start=t,this.drawRange.count=e}applyMatrix4(t){let e=this.attributes.position;e!==void 0&&(e.applyMatrix4(t),e.needsUpdate=!0);let n=this.attributes.normal;if(n!==void 0){let r=new ee().getNormalMatrix(t);n.applyNormalMatrix(r),n.needsUpdate=!0}let s=this.attributes.tangent;return s!==void 0&&(s.transformDirection(t),s.needsUpdate=!0),this.boundingBox!==null&&this.computeBoundingBox(),this.boundingSphere!==null&&this.computeBoundingSphere(),this._transformed=!0,this}applyQuaternion(t){return Hn.makeRotationFromQuaternion(t),this.applyMatrix4(Hn),this}rotateX(t){return Hn.makeRotationX(t),this.applyMatrix4(Hn),this}rotateY(t){return Hn.makeRotationY(t),this.applyMatrix4(Hn),this}rotateZ(t){return Hn.makeRotationZ(t),this.applyMatrix4(Hn),this}translate(t,e,n){return Hn.makeTranslation(t,e,n),this.applyMatrix4(Hn),this}scale(t,e,n){return Hn.makeScale(t,e,n),this.applyMatrix4(Hn),this}lookAt(t){return dc.lookAt(t),dc.updateMatrix(),this.applyMatrix4(dc.matrix),this}center(){return this.computeBoundingBox(),this.boundingBox.getCenter(ar).negate(),this.translate(ar.x,ar.y,ar.z),this}setFromPoints(t){let e=this.getAttribute("position");if(e===void 0){let n=[];for(let s=0,r=t.length;s<r;s++){let a=t[s];n.push(a.x,a.y,a.z||0)}this.setAttribute("position",new Fe(n,3))}else{let n=Math.min(t.length,e.count);for(let s=0;s<n;s++){let r=t[s];e.setXYZ(s,r.x,r.y,r.z||0)}t.length>e.count&&Zt("BufferGeometry: Buffer size too small for points data. Use .dispose() and create a new geometry."),e.needsUpdate=!0}return this}computeBoundingBox(){this.boundingBox===null&&(this.boundingBox=new _i);let t=this.attributes.position,e=this.morphAttributes.position;if(t&&t.isGLBufferAttribute){$t("BufferGeometry.computeBoundingBox(): GLBufferAttribute requires a manual bounding box.",this),this.boundingBox.set(new O(-1/0,-1/0,-1/0),new O(1/0,1/0,1/0));return}if(t!==void 0){if(this.boundingBox.setFromBufferAttribute(t),e)for(let n=0,s=e.length;n<s;n++){let r=e[n];Ln.setFromBufferAttribute(r),this.morphTargetsRelative?(Qe.addVectors(this.boundingBox.min,Ln.min),this.boundingBox.expandByPoint(Qe),Qe.addVectors(this.boundingBox.max,Ln.max),this.boundingBox.expandByPoint(Qe)):(this.boundingBox.expandByPoint(Ln.min),this.boundingBox.expandByPoint(Ln.max))}}else this.boundingBox.makeEmpty();(isNaN(this.boundingBox.min.x)||isNaN(this.boundingBox.min.y)||isNaN(this.boundingBox.min.z))&&$t('BufferGeometry.computeBoundingBox(): Computed min/max have NaN values. The "position" attribute is likely to have NaN values.',this)}computeBoundingSphere(){this.boundingSphere===null&&(this.boundingSphere=new as);let t=this.attributes.position,e=this.morphAttributes.position;if(t&&t.isGLBufferAttribute){$t("BufferGeometry.computeBoundingSphere(): GLBufferAttribute requires a manual bounding sphere.",this),this.boundingSphere.set(new O,1/0);return}if(t){let n=this.boundingSphere.center;if(Ln.setFromBufferAttribute(t),e)for(let r=0,a=e.length;r<a;r++){let o=e[r];Jr.setFromBufferAttribute(o),this.morphTargetsRelative?(Qe.addVectors(Ln.min,Jr.min),Ln.expandByPoint(Qe),Qe.addVectors(Ln.max,Jr.max),Ln.expandByPoint(Qe)):(Ln.expandByPoint(Jr.min),Ln.expandByPoint(Jr.max))}Ln.getCenter(n);let s=0;for(let r=0,a=t.count;r<a;r++)Qe.fromBufferAttribute(t,r),s=Math.max(s,n.distanceToSquared(Qe));if(e)for(let r=0,a=e.length;r<a;r++){let o=e[r],l=this.morphTargetsRelative;for(let c=0,h=o.count;c<h;c++)Qe.fromBufferAttribute(o,c),l&&(ar.fromBufferAttribute(t,c),Qe.add(ar)),s=Math.max(s,n.distanceToSquared(Qe))}this.boundingSphere.radius=Math.sqrt(s),isNaN(this.boundingSphere.radius)&&$t('BufferGeometry.computeBoundingSphere(): Computed radius is NaN. The "position" attribute is likely to have NaN values.',this)}}computeTangents(){let t=this.index,e=this.attributes;if(t===null||e.position===void 0||e.normal===void 0||e.uv===void 0){$t("BufferGeometry: .computeTangents() failed. Missing required attributes (index, position, normal or uv)");return}let n=e.position,s=e.normal,r=e.uv,a=this.getAttribute("tangent");(a===void 0||a.count!==n.count)&&(a=new on(new Float32Array(4*n.count),4),this.setAttribute("tangent",a));let o=[],l=[];for(let g=0;g<n.count;g++)o[g]=new O,l[g]=new O;let c=new O,h=new O,p=new O,d=new qt,f=new qt,_=new qt,b=new O,m=new O;function u(g,w,T){c.fromBufferAttribute(n,g),h.fromBufferAttribute(n,w),p.fromBufferAttribute(n,T),d.fromBufferAttribute(r,g),f.fromBufferAttribute(r,w),_.fromBufferAttribute(r,T),h.sub(c),p.sub(c),f.sub(d),_.sub(d);let I=1/(f.x*_.y-_.x*f.y);isFinite(I)&&(b.copy(h).multiplyScalar(_.y).addScaledVector(p,-f.y).multiplyScalar(I),m.copy(p).multiplyScalar(f.x).addScaledVector(h,-_.x).multiplyScalar(I),o[g].add(b),o[w].add(b),o[T].add(b),l[g].add(m),l[w].add(m),l[T].add(m))}let S=this.groups;S.length===0&&(S=[{start:0,count:t.count}]);for(let g=0,w=S.length;g<w;++g){let T=S[g],I=T.start,N=T.count;for(let B=I,F=I+N;B<F;B+=3)u(t.getX(B+0),t.getX(B+1),t.getX(B+2))}let R=new O,v=new O,M=new O,E=new O;function A(g){M.fromBufferAttribute(s,g),E.copy(M);let w=o[g];R.copy(w),R.sub(M.multiplyScalar(M.dot(w))).normalize(),v.crossVectors(E,w);let I=v.dot(l[g])<0?-1:1;a.setXYZW(g,R.x,R.y,R.z,I)}for(let g=0,w=S.length;g<w;++g){let T=S[g],I=T.start,N=T.count;for(let B=I,F=I+N;B<F;B+=3)A(t.getX(B+0)),A(t.getX(B+1)),A(t.getX(B+2))}this._transformed=!0}computeVertexNormals(){let t=this.index,e=this.getAttribute("position");if(e!==void 0){let n=this.getAttribute("normal");if(n===void 0||n.count!==e.count)n=new on(new Float32Array(e.count*3),3),this.setAttribute("normal",n);else for(let d=0,f=n.count;d<f;d++)n.setXYZ(d,0,0,0);let s=new O,r=new O,a=new O,o=new O,l=new O,c=new O,h=new O,p=new O;if(t)for(let d=0,f=t.count;d<f;d+=3){let _=t.getX(d+0),b=t.getX(d+1),m=t.getX(d+2);s.fromBufferAttribute(e,_),r.fromBufferAttribute(e,b),a.fromBufferAttribute(e,m),h.subVectors(a,r),p.subVectors(s,r),h.cross(p),o.fromBufferAttribute(n,_),l.fromBufferAttribute(n,b),c.fromBufferAttribute(n,m),o.add(h),l.add(h),c.add(h),n.setXYZ(_,o.x,o.y,o.z),n.setXYZ(b,l.x,l.y,l.z),n.setXYZ(m,c.x,c.y,c.z)}else for(let d=0,f=e.count;d<f;d+=3)s.fromBufferAttribute(e,d+0),r.fromBufferAttribute(e,d+1),a.fromBufferAttribute(e,d+2),h.subVectors(a,r),p.subVectors(s,r),h.cross(p),n.setXYZ(d+0,h.x,h.y,h.z),n.setXYZ(d+1,h.x,h.y,h.z),n.setXYZ(d+2,h.x,h.y,h.z);this.normalizeNormals(),n.needsUpdate=!0}}normalizeNormals(){let t=this.attributes.normal;for(let e=0,n=t.count;e<n;e++)Qe.fromBufferAttribute(t,e),Qe.normalize(),t.setXYZ(e,Qe.x,Qe.y,Qe.z)}toNonIndexed(){function t(o,l){let c=o.array,h=o.itemSize,p=o.normalized,d=new c.constructor(l.length*h),f=0,_=0;for(let b=0,m=l.length;b<m;b++){o.isInterleavedBufferAttribute?f=l[b]*o.data.stride+o.offset:f=l[b]*h;for(let u=0;u<h;u++)d[_++]=c[f++]}return new on(d,h,p)}if(this.index===null)return Zt("BufferGeometry.toNonIndexed(): BufferGeometry is already non-indexed."),this;let e=new i,n=this.index.array,s=this.attributes;for(let o in s){let l=s[o],c=t(l,n);e.setAttribute(o,c)}let r=this.morphAttributes;for(let o in r){let l=[],c=r[o];for(let h=0,p=c.length;h<p;h++){let d=c[h],f=t(d,n);l.push(f)}e.morphAttributes[o]=l}e.morphTargetsRelative=this.morphTargetsRelative;let a=this.groups;for(let o=0,l=a.length;o<l;o++){let c=a[o];e.addGroup(c.start,c.count,c.materialIndex)}return e}toJSON(){let t={metadata:{version:4.7,type:"BufferGeometry",generator:"BufferGeometry.toJSON"}};if(t.uuid=this.uuid,t.type=this.parameters!==void 0&&this._transformed===!0?"BufferGeometry":this.type,t.name=this.name,Object.keys(this.userData).length>0&&(t.userData=this.userData),this.parameters!==void 0&&this._transformed!==!0){let l=this.parameters;for(let c in l)l[c]!==void 0&&(t[c]=l[c]);return t}t.data={attributes:{}};let e=this.index;e!==null&&(t.data.index={type:e.array.constructor.name,array:Array.prototype.slice.call(e.array)});let n=this.attributes;for(let l in n){let c=n[l];t.data.attributes[l]=c.toJSON(t.data)}let s={},r=!1;for(let l in this.morphAttributes){let c=this.morphAttributes[l],h=[];for(let p=0,d=c.length;p<d;p++){let f=c[p];h.push(f.toJSON(t.data))}h.length>0&&(s[l]=h,r=!0)}r&&(t.data.morphAttributes=s,t.data.morphTargetsRelative=this.morphTargetsRelative);let a=this.groups;a.length>0&&(t.data.groups=JSON.parse(JSON.stringify(a)));let o=this.boundingSphere;return o!==null&&(t.data.boundingSphere=o.toJSON()),t}clone(){return new this.constructor().copy(this)}copy(t){this.index=null,this.attributes={},this.morphAttributes={},this.groups=[],this.boundingBox=null,this.boundingSphere=null;let e={};this.name=t.name;let n=t.index;n!==null&&this.setIndex(n.clone());let s=t.attributes;for(let c in s){let h=s[c];this.setAttribute(c,h.clone(e))}let r=t.morphAttributes;for(let c in r){let h=[],p=r[c];for(let d=0,f=p.length;d<f;d++)h.push(p[d].clone(e));this.morphAttributes[c]=h}this.morphTargetsRelative=t.morphTargetsRelative;let a=t.groups;for(let c=0,h=a.length;c<h;c++){let p=a[c];this.addGroup(p.start,p.count,p.materialIndex)}let o=t.boundingBox;o!==null&&(this.boundingBox=o.clone());let l=t.boundingSphere;return l!==null&&(this.boundingSphere=l.clone()),this.drawRange.start=t.drawRange.start,this.drawRange.count=t.drawRange.count,this.userData=t.userData,this._transformed=t._transformed,this}dispose(){this.dispatchEvent({type:"dispose"})}};var fc=new O,Xf=new O,qf=new ee,Dn=class{constructor(t=new O(1,0,0),e=0){this.isPlane=!0,this.normal=t,this.constant=e}set(t,e){return this.normal.copy(t),this.constant=e,this}setComponents(t,e,n,s){return this.normal.set(t,e,n),this.constant=s,this}setFromNormalAndCoplanarPoint(t,e){return this.normal.copy(t),this.constant=-e.dot(this.normal),this}setFromCoplanarPoints(t,e,n){let s=fc.subVectors(n,e).cross(Xf.subVectors(t,e)).normalize();return this.setFromNormalAndCoplanarPoint(s,t),this}copy(t){return this.normal.copy(t.normal),this.constant=t.constant,this}normalize(){let t=1/this.normal.length();return this.normal.multiplyScalar(t),this.constant*=t,this}negate(){return this.constant*=-1,this.normal.negate(),this}distanceToPoint(t){return this.normal.dot(t)+this.constant}distanceToSphere(t){return this.distanceToPoint(t.center)-t.radius}projectPoint(t,e){return e.copy(t).addScaledVector(this.normal,-this.distanceToPoint(t))}intersectLine(t,e,n=!0){let s=t.delta(fc),r=this.normal.dot(s);if(r===0)return this.distanceToPoint(t.start)===0?e.copy(t.start):null;let a=-(t.start.dot(this.normal)+this.constant)/r;return n===!0&&(a<0||a>1)?null:e.copy(t.start).addScaledVector(s,a)}intersectsLine(t){let e=this.distanceToPoint(t.start),n=this.distanceToPoint(t.end);return e<0&&n>0||n<0&&e>0}intersectsBox(t){return t.intersectsPlane(this)}intersectsSphere(t){return t.intersectsPlane(this)}coplanarPoint(t){return t.copy(this.normal).multiplyScalar(-this.constant)}applyMatrix4(t,e){let n=e||qf.getNormalMatrix(t),s=this.coplanarPoint(fc).applyMatrix4(t),r=this.normal.applyMatrix3(n).normalize();return this.constant=-s.dot(r),this}translate(t){return this.constant-=t.dot(this.normal),this}equals(t){return t.normal.equals(this.normal)&&t.constant===this.constant}clone(){return new this.constructor().copy(this)}toJSON(){return{normal:this.normal.toArray(),constant:this.constant}}fromJSON(t){return this.normal.fromArray(t.normal),this.constant=t.constant,this}},Yf=0,os=class extends ii{constructor(){super(),this.isMaterial=!0,Object.defineProperty(this,"id",{value:Yf++}),this.uuid=Cr(),this.name="",this.type="Material",this.blending=Tr,this.side=ps,this.vertexColors=!1,this.opacity=1,this.transparent=!1,this.alphaHash=!1,this.blendSrc=Ic,this.blendDst=Lc,this.blendEquation=Os,this.blendSrcAlpha=null,this.blendDstAlpha=null,this.blendEquationAlpha=null,this.blendColor=new jt(0,0,0),this.blendAlpha=0,this.depthFunc=fr,this.depthTest=!0,this.depthWrite=!0,this.stencilWriteMask=255,this.stencilFunc=Ou,this.stencilRef=0,this.stencilFuncMask=255,this.stencilFail=oo,this.stencilZFail=oo,this.stencilZPass=oo,this.stencilWrite=!1,this.clippingPlanes=null,this.clipIntersection=!1,this.clipShadows=!1,this.shadowSide=null,this.colorWrite=!0,this.precision=null,this.polygonOffset=!1,this.polygonOffsetFactor=0,this.polygonOffsetUnits=0,this.dithering=!1,this.alphaToCoverage=!1,this.premultipliedAlpha=!1,this.forceSinglePass=!1,this.allowOverride=!0,this.visible=!0,this.toneMapped=!0,this.userData={},this.version=0,this._alphaTest=0}get alphaTest(){return this._alphaTest}set alphaTest(t){this._alphaTest>0!=t>0&&this.version++,this._alphaTest=t}onBeforeRender(){}onBeforeCompile(){}customProgramCacheKey(){return this.onBeforeCompile.toString()}setValues(t){if(t!==void 0)for(let e in t){let n=t[e];if(n===void 0){Zt(`Material: parameter '${e}' has value of undefined.`);continue}let s=this[e];if(s===void 0){Zt(`Material: '${e}' is not a property of THREE.${this.type}.`);continue}s&&s.isColor?s.set(n):s&&s.isVector2&&n&&n.isVector2||s&&s.isEuler&&n&&n.isEuler||s&&s.isVector3&&n&&n.isVector3?s.copy(n):this[e]=n}}toJSON(t){let e=t===void 0||typeof t=="string";e&&(t={textures:{},images:{}});let n={metadata:{version:4.7,type:"Material",generator:"Material.toJSON"}};n.uuid=this.uuid,n.type=this.type,n.blending=this.blending,n.side=this.side,n.shadowSide=this.shadowSide,n.vertexColors=this.vertexColors,n.opacity=this.opacity,n.transparent=this.transparent,n.blendSrc=this.blendSrc,n.blendDst=this.blendDst,n.blendEquation=this.blendEquation,n.blendSrcAlpha=this.blendSrcAlpha,n.blendDstAlpha=this.blendDstAlpha,n.blendEquationAlpha=this.blendEquationAlpha,n.blendColor=this.blendColor.getHex(),n.blendAlpha=this.blendAlpha,n.depthFunc=this.depthFunc,n.depthTest=this.depthTest,n.depthWrite=this.depthWrite,n.colorWrite=this.colorWrite,n.clipIntersection=this.clipIntersection,n.clipShadows=this.clipShadows,n.stencilWriteMask=this.stencilWriteMask,n.stencilFunc=this.stencilFunc,n.stencilRef=this.stencilRef,n.stencilFuncMask=this.stencilFuncMask,n.stencilFail=this.stencilFail,n.stencilZFail=this.stencilZFail,n.stencilZPass=this.stencilZPass,n.stencilWrite=this.stencilWrite,n.polygonOffset=this.polygonOffset,n.polygonOffsetFactor=this.polygonOffsetFactor,n.polygonOffsetUnits=this.polygonOffsetUnits,n.dithering=this.dithering,n.alphaTest=this.alphaTest,n.alphaHash=this.alphaHash,n.alphaToCoverage=this.alphaToCoverage,n.premultipliedAlpha=this.premultipliedAlpha,n.forceSinglePass=this.forceSinglePass,n.allowOverride=this.allowOverride,n.visible=this.visible,n.toneMapped=this.toneMapped,n.name=this.name,this.color&&this.color.isColor&&(n.color=this.color.getHex()),this.roughness!==void 0&&(n.roughness=this.roughness),this.metalness!==void 0&&(n.metalness=this.metalness),this.sheen!==void 0&&(n.sheen=this.sheen),this.sheenColor&&this.sheenColor.isColor&&(n.sheenColor=this.sheenColor.getHex()),this.sheenRoughness!==void 0&&(n.sheenRoughness=this.sheenRoughness),this.emissive&&this.emissive.isColor&&(n.emissive=this.emissive.getHex()),this.emissiveIntensity!==void 0&&(n.emissiveIntensity=this.emissiveIntensity),this.specular&&this.specular.isColor&&(n.specular=this.specular.getHex()),this.specularIntensity!==void 0&&(n.specularIntensity=this.specularIntensity),this.specularColor&&this.specularColor.isColor&&(n.specularColor=this.specularColor.getHex()),this.shininess!==void 0&&(n.shininess=this.shininess),this.clearcoat!==void 0&&(n.clearcoat=this.clearcoat),this.clearcoatRoughness!==void 0&&(n.clearcoatRoughness=this.clearcoatRoughness),this.clearcoatMap&&this.clearcoatMap.isTexture&&(n.clearcoatMap=this.clearcoatMap.toJSON(t).uuid),this.clearcoatRoughnessMap&&this.clearcoatRoughnessMap.isTexture&&(n.clearcoatRoughnessMap=this.clearcoatRoughnessMap.toJSON(t).uuid),this.clearcoatNormalMap&&this.clearcoatNormalMap.isTexture&&(n.clearcoatNormalMap=this.clearcoatNormalMap.toJSON(t).uuid,n.clearcoatNormalScale=this.clearcoatNormalScale.toArray()),this.sheenColorMap&&this.sheenColorMap.isTexture&&(n.sheenColorMap=this.sheenColorMap.toJSON(t).uuid),this.sheenRoughnessMap&&this.sheenRoughnessMap.isTexture&&(n.sheenRoughnessMap=this.sheenRoughnessMap.toJSON(t).uuid),this.dispersion!==void 0&&(n.dispersion=this.dispersion),this.retroreflectivity!==void 0&&(n.retroreflectivity=this.retroreflectivity),this.iridescence!==void 0&&(n.iridescence=this.iridescence),this.iridescenceIOR!==void 0&&(n.iridescenceIOR=this.iridescenceIOR),this.iridescenceThicknessRange!==void 0&&(n.iridescenceThicknessRange=this.iridescenceThicknessRange),this.iridescenceMap&&this.iridescenceMap.isTexture&&(n.iridescenceMap=this.iridescenceMap.toJSON(t).uuid),this.iridescenceThicknessMap&&this.iridescenceThicknessMap.isTexture&&(n.iridescenceThicknessMap=this.iridescenceThicknessMap.toJSON(t).uuid),this.anisotropy!==void 0&&(n.anisotropy=this.anisotropy),this.anisotropyRotation!==void 0&&(n.anisotropyRotation=this.anisotropyRotation),this.anisotropyMap&&this.anisotropyMap.isTexture&&(n.anisotropyMap=this.anisotropyMap.toJSON(t).uuid),this.map&&this.map.isTexture&&(n.map=this.map.toJSON(t).uuid),this.matcap&&this.matcap.isTexture&&(n.matcap=this.matcap.toJSON(t).uuid),this.alphaMap&&this.alphaMap.isTexture&&(n.alphaMap=this.alphaMap.toJSON(t).uuid),this.lightMap&&this.lightMap.isTexture&&(n.lightMap=this.lightMap.toJSON(t).uuid,n.lightMapIntensity=this.lightMapIntensity),this.aoMap&&this.aoMap.isTexture&&(n.aoMap=this.aoMap.toJSON(t).uuid,n.aoMapIntensity=this.aoMapIntensity),this.bumpMap&&this.bumpMap.isTexture&&(n.bumpMap=this.bumpMap.toJSON(t).uuid,n.bumpScale=this.bumpScale),this.normalMap&&this.normalMap.isTexture&&(n.normalMap=this.normalMap.toJSON(t).uuid,n.normalMapType=this.normalMapType,n.normalScale=this.normalScale.toArray()),this.displacementMap&&this.displacementMap.isTexture&&(n.displacementMap=this.displacementMap.toJSON(t).uuid,n.displacementScale=this.displacementScale,n.displacementBias=this.displacementBias),this.roughnessMap&&this.roughnessMap.isTexture&&(n.roughnessMap=this.roughnessMap.toJSON(t).uuid),this.metalnessMap&&this.metalnessMap.isTexture&&(n.metalnessMap=this.metalnessMap.toJSON(t).uuid),this.emissiveMap&&this.emissiveMap.isTexture&&(n.emissiveMap=this.emissiveMap.toJSON(t).uuid),this.specularMap&&this.specularMap.isTexture&&(n.specularMap=this.specularMap.toJSON(t).uuid),this.specularIntensityMap&&this.specularIntensityMap.isTexture&&(n.specularIntensityMap=this.specularIntensityMap.toJSON(t).uuid),this.specularColorMap&&this.specularColorMap.isTexture&&(n.specularColorMap=this.specularColorMap.toJSON(t).uuid),this.envMap&&this.envMap.isTexture&&(n.envMap=this.envMap.toJSON(t).uuid,this.combine!==void 0&&(n.combine=this.combine)),this.envMapRotation!==void 0&&(n.envMapRotation=this.envMapRotation.toArray()),this.envMapIntensity!==void 0&&(n.envMapIntensity=this.envMapIntensity),this.reflectivity!==void 0&&(n.reflectivity=this.reflectivity),this.refractionRatio!==void 0&&(n.refractionRatio=this.refractionRatio),this.gradientMap&&this.gradientMap.isTexture&&(n.gradientMap=this.gradientMap.toJSON(t).uuid),this.transmission!==void 0&&(n.transmission=this.transmission),this.transmissionMap&&this.transmissionMap.isTexture&&(n.transmissionMap=this.transmissionMap.toJSON(t).uuid),this.thickness!==void 0&&(n.thickness=this.thickness),this.thicknessMap&&this.thicknessMap.isTexture&&(n.thicknessMap=this.thicknessMap.toJSON(t).uuid),this.attenuationDistance!==void 0&&(n.attenuationDistance=this.attenuationDistance),this.attenuationColor!==void 0&&(n.attenuationColor=this.attenuationColor.getHex()),this.size!==void 0&&(n.size=this.size),this.sizeAttenuation!==void 0&&(n.sizeAttenuation=this.sizeAttenuation),Array.isArray(this.clippingPlanes)&&this.clippingPlanes.length>0&&(n.clippingPlanes=this.clippingPlanes.map(r=>r.toJSON())),this.rotation!==void 0&&(n.rotation=this.rotation),this.depthPacking!==void 0&&(n.depthPacking=this.depthPacking),this.linewidth!==void 0&&(n.linewidth=this.linewidth),this.linecap!==void 0&&(n.linecap=this.linecap),this.linejoin!==void 0&&(n.linejoin=this.linejoin),this.dashSize!==void 0&&(n.dashSize=this.dashSize),this.gapSize!==void 0&&(n.gapSize=this.gapSize),this.scale!==void 0&&(n.scale=this.scale),this.wireframe!==void 0&&(n.wireframe=this.wireframe),this.wireframeLinewidth!==void 0&&(n.wireframeLinewidth=this.wireframeLinewidth),this.wireframeLinecap!==void 0&&(n.wireframeLinecap=this.wireframeLinecap),this.wireframeLinejoin!==void 0&&(n.wireframeLinejoin=this.wireframeLinejoin),this.flatShading!==void 0&&(n.flatShading=this.flatShading),this.fog!==void 0&&(n.fog=this.fog),Object.keys(this.userData).length>0&&(n.userData=this.userData);function s(r){let a=[];for(let o in r){let l=r[o];delete l.metadata,a.push(l)}return a}if(e){let r=s(t.textures),a=s(t.images);r.length>0&&(n.textures=r),a.length>0&&(n.images=a)}return n}fromJSON(t,e){if(t.uuid!==void 0&&(this.uuid=t.uuid),t.name!==void 0&&(this.name=t.name),t.color!==void 0&&this.color!==void 0&&this.color.setHex(t.color),t.roughness!==void 0&&(this.roughness=t.roughness),t.metalness!==void 0&&(this.metalness=t.metalness),t.sheen!==void 0&&(this.sheen=t.sheen),t.sheenColor!==void 0&&(this.sheenColor=new jt().setHex(t.sheenColor)),t.sheenRoughness!==void 0&&(this.sheenRoughness=t.sheenRoughness),t.emissive!==void 0&&this.emissive!==void 0&&this.emissive.setHex(t.emissive),t.specular!==void 0&&this.specular!==void 0&&this.specular.setHex(t.specular),t.specularIntensity!==void 0&&(this.specularIntensity=t.specularIntensity),t.specularColor!==void 0&&this.specularColor!==void 0&&this.specularColor.setHex(t.specularColor),t.shininess!==void 0&&(this.shininess=t.shininess),t.clearcoat!==void 0&&(this.clearcoat=t.clearcoat),t.clearcoatRoughness!==void 0&&(this.clearcoatRoughness=t.clearcoatRoughness),t.dispersion!==void 0&&(this.dispersion=t.dispersion),t.retroreflectivity!==void 0&&(this.retroreflectivity=t.retroreflectivity),t.iridescence!==void 0&&(this.iridescence=t.iridescence),t.iridescenceIOR!==void 0&&(this.iridescenceIOR=t.iridescenceIOR),t.iridescenceThicknessRange!==void 0&&(this.iridescenceThicknessRange=t.iridescenceThicknessRange),t.transmission!==void 0&&(this.transmission=t.transmission),t.thickness!==void 0&&(this.thickness=t.thickness),t.attenuationDistance!==void 0&&(this.attenuationDistance=t.attenuationDistance),t.attenuationColor!==void 0&&this.attenuationColor!==void 0&&this.attenuationColor.setHex(t.attenuationColor),t.anisotropy!==void 0&&(this.anisotropy=t.anisotropy),t.anisotropyRotation!==void 0&&(this.anisotropyRotation=t.anisotropyRotation),t.fog!==void 0&&(this.fog=t.fog),t.flatShading!==void 0&&(this.flatShading=t.flatShading),t.blending!==void 0&&(this.blending=t.blending),t.combine!==void 0&&(this.combine=t.combine),t.side!==void 0&&(this.side=t.side),t.shadowSide!==void 0&&(this.shadowSide=t.shadowSide),t.opacity!==void 0&&(this.opacity=t.opacity),t.transparent!==void 0&&(this.transparent=t.transparent),t.alphaTest!==void 0&&(this.alphaTest=t.alphaTest),t.alphaHash!==void 0&&(this.alphaHash=t.alphaHash),t.depthFunc!==void 0&&(this.depthFunc=t.depthFunc),t.depthTest!==void 0&&(this.depthTest=t.depthTest),t.depthWrite!==void 0&&(this.depthWrite=t.depthWrite),t.colorWrite!==void 0&&(this.colorWrite=t.colorWrite),t.clippingPlanes!==void 0&&(this.clippingPlanes=t.clippingPlanes.map(n=>new Dn().fromJSON(n))),t.clipIntersection!==void 0&&(this.clipIntersection=t.clipIntersection),t.clipShadows!==void 0&&(this.clipShadows=t.clipShadows),t.depthPacking!==void 0&&(this.depthPacking=t.depthPacking),t.blendSrc!==void 0&&(this.blendSrc=t.blendSrc),t.blendDst!==void 0&&(this.blendDst=t.blendDst),t.blendEquation!==void 0&&(this.blendEquation=t.blendEquation),t.blendSrcAlpha!==void 0&&(this.blendSrcAlpha=t.blendSrcAlpha),t.blendDstAlpha!==void 0&&(this.blendDstAlpha=t.blendDstAlpha),t.blendEquationAlpha!==void 0&&(this.blendEquationAlpha=t.blendEquationAlpha),t.blendColor!==void 0&&this.blendColor!==void 0&&this.blendColor.setHex(t.blendColor),t.blendAlpha!==void 0&&(this.blendAlpha=t.blendAlpha),t.stencilWriteMask!==void 0&&(this.stencilWriteMask=t.stencilWriteMask),t.stencilFunc!==void 0&&(this.stencilFunc=t.stencilFunc),t.stencilRef!==void 0&&(this.stencilRef=t.stencilRef),t.stencilFuncMask!==void 0&&(this.stencilFuncMask=t.stencilFuncMask),t.stencilFail!==void 0&&(this.stencilFail=t.stencilFail),t.stencilZFail!==void 0&&(this.stencilZFail=t.stencilZFail),t.stencilZPass!==void 0&&(this.stencilZPass=t.stencilZPass),t.stencilWrite!==void 0&&(this.stencilWrite=t.stencilWrite),t.wireframe!==void 0&&(this.wireframe=t.wireframe),t.wireframeLinewidth!==void 0&&(this.wireframeLinewidth=t.wireframeLinewidth),t.wireframeLinecap!==void 0&&(this.wireframeLinecap=t.wireframeLinecap),t.wireframeLinejoin!==void 0&&(this.wireframeLinejoin=t.wireframeLinejoin),t.rotation!==void 0&&(this.rotation=t.rotation),t.linewidth!==void 0&&(this.linewidth=t.linewidth),t.linecap!==void 0&&(this.linecap=t.linecap),t.linejoin!==void 0&&(this.linejoin=t.linejoin),t.dashSize!==void 0&&(this.dashSize=t.dashSize),t.gapSize!==void 0&&(this.gapSize=t.gapSize),t.scale!==void 0&&(this.scale=t.scale),t.polygonOffset!==void 0&&(this.polygonOffset=t.polygonOffset),t.polygonOffsetFactor!==void 0&&(this.polygonOffsetFactor=t.polygonOffsetFactor),t.polygonOffsetUnits!==void 0&&(this.polygonOffsetUnits=t.polygonOffsetUnits),t.dithering!==void 0&&(this.dithering=t.dithering),t.alphaToCoverage!==void 0&&(this.alphaToCoverage=t.alphaToCoverage),t.premultipliedAlpha!==void 0&&(this.premultipliedAlpha=t.premultipliedAlpha),t.forceSinglePass!==void 0&&(this.forceSinglePass=t.forceSinglePass),t.allowOverride!==void 0&&(this.allowOverride=t.allowOverride),t.visible!==void 0&&(this.visible=t.visible),t.toneMapped!==void 0&&(this.toneMapped=t.toneMapped),t.userData!==void 0&&(this.userData=t.userData),t.vertexColors!==void 0&&(typeof t.vertexColors=="number"?this.vertexColors=t.vertexColors>0:this.vertexColors=t.vertexColors),t.size!==void 0&&(this.size=t.size),t.sizeAttenuation!==void 0&&(this.sizeAttenuation=t.sizeAttenuation),t.map!==void 0&&(this.map=e[t.map]||null),t.matcap!==void 0&&(this.matcap=e[t.matcap]||null),t.alphaMap!==void 0&&(this.alphaMap=e[t.alphaMap]||null),t.bumpMap!==void 0&&(this.bumpMap=e[t.bumpMap]||null),t.bumpScale!==void 0&&(this.bumpScale=t.bumpScale),t.normalMap!==void 0&&(this.normalMap=e[t.normalMap]||null),t.normalMapType!==void 0&&(this.normalMapType=t.normalMapType),t.normalScale!==void 0){let n=t.normalScale;Array.isArray(n)===!1&&(n=[n,n]),this.normalScale=new qt().fromArray(n)}return t.displacementMap!==void 0&&(this.displacementMap=e[t.displacementMap]||null),t.displacementScale!==void 0&&(this.displacementScale=t.displacementScale),t.displacementBias!==void 0&&(this.displacementBias=t.displacementBias),t.roughnessMap!==void 0&&(this.roughnessMap=e[t.roughnessMap]||null),t.metalnessMap!==void 0&&(this.metalnessMap=e[t.metalnessMap]||null),t.emissiveMap!==void 0&&(this.emissiveMap=e[t.emissiveMap]||null),t.emissiveIntensity!==void 0&&(this.emissiveIntensity=t.emissiveIntensity),t.specularMap!==void 0&&(this.specularMap=e[t.specularMap]||null),t.specularIntensityMap!==void 0&&(this.specularIntensityMap=e[t.specularIntensityMap]||null),t.specularColorMap!==void 0&&(this.specularColorMap=e[t.specularColorMap]||null),t.envMap!==void 0&&(this.envMap=e[t.envMap]||null),t.envMapRotation!==void 0&&this.envMapRotation.fromArray(t.envMapRotation),t.envMapIntensity!==void 0&&(this.envMapIntensity=t.envMapIntensity),t.reflectivity!==void 0&&(this.reflectivity=t.reflectivity),t.refractionRatio!==void 0&&(this.refractionRatio=t.refractionRatio),t.lightMap!==void 0&&(this.lightMap=e[t.lightMap]||null),t.lightMapIntensity!==void 0&&(this.lightMapIntensity=t.lightMapIntensity),t.aoMap!==void 0&&(this.aoMap=e[t.aoMap]||null),t.aoMapIntensity!==void 0&&(this.aoMapIntensity=t.aoMapIntensity),t.gradientMap!==void 0&&(this.gradientMap=e[t.gradientMap]||null),t.clearcoatMap!==void 0&&(this.clearcoatMap=e[t.clearcoatMap]||null),t.clearcoatRoughnessMap!==void 0&&(this.clearcoatRoughnessMap=e[t.clearcoatRoughnessMap]||null),t.clearcoatNormalMap!==void 0&&(this.clearcoatNormalMap=e[t.clearcoatNormalMap]||null),t.clearcoatNormalScale!==void 0&&(this.clearcoatNormalScale=new qt().fromArray(t.clearcoatNormalScale)),t.iridescenceMap!==void 0&&(this.iridescenceMap=e[t.iridescenceMap]||null),t.iridescenceThicknessMap!==void 0&&(this.iridescenceThicknessMap=e[t.iridescenceThicknessMap]||null),t.transmissionMap!==void 0&&(this.transmissionMap=e[t.transmissionMap]||null),t.thicknessMap!==void 0&&(this.thicknessMap=e[t.thicknessMap]||null),t.anisotropyMap!==void 0&&(this.anisotropyMap=e[t.anisotropyMap]||null),t.sheenColorMap!==void 0&&(this.sheenColorMap=e[t.sheenColorMap]||null),t.sheenRoughnessMap!==void 0&&(this.sheenRoughnessMap=e[t.sheenRoughnessMap]||null),this}clone(){return new this.constructor().copy(this)}copy(t){this.name=t.name,this.blending=t.blending,this.side=t.side,this.vertexColors=t.vertexColors,this.opacity=t.opacity,this.transparent=t.transparent,this.blendSrc=t.blendSrc,this.blendDst=t.blendDst,this.blendEquation=t.blendEquation,this.blendSrcAlpha=t.blendSrcAlpha,this.blendDstAlpha=t.blendDstAlpha,this.blendEquationAlpha=t.blendEquationAlpha,this.blendColor.copy(t.blendColor),this.blendAlpha=t.blendAlpha,this.depthFunc=t.depthFunc,this.depthTest=t.depthTest,this.depthWrite=t.depthWrite,this.stencilWriteMask=t.stencilWriteMask,this.stencilFunc=t.stencilFunc,this.stencilRef=t.stencilRef,this.stencilFuncMask=t.stencilFuncMask,this.stencilFail=t.stencilFail,this.stencilZFail=t.stencilZFail,this.stencilZPass=t.stencilZPass,this.stencilWrite=t.stencilWrite;let e=t.clippingPlanes,n=null;if(e!==null){let s=e.length;n=new Array(s);for(let r=0;r!==s;++r)n[r]=e[r].clone()}return this.clippingPlanes=n,this.clipIntersection=t.clipIntersection,this.clipShadows=t.clipShadows,this.shadowSide=t.shadowSide,this.colorWrite=t.colorWrite,this.precision=t.precision,this.polygonOffset=t.polygonOffset,this.polygonOffsetFactor=t.polygonOffsetFactor,this.polygonOffsetUnits=t.polygonOffsetUnits,this.dithering=t.dithering,this.alphaTest=t.alphaTest,this.alphaHash=t.alphaHash,this.alphaToCoverage=t.alphaToCoverage,this.premultipliedAlpha=t.premultipliedAlpha,this.forceSinglePass=t.forceSinglePass,this.allowOverride=t.allowOverride,this.visible=t.visible,this.toneMapped=t.toneMapped,this.userData=JSON.parse(JSON.stringify(t.userData)),this}dispose(){this.dispatchEvent({type:"dispose"})}set needsUpdate(t){t===!0&&this.version++}};var Oi=new O,pc=new O,Ya=new O,Za=new O,zs=class{constructor(t=new O,e=new O(0,0,-1)){this.origin=t,this.direction=e}set(t,e){return this.origin.copy(t),this.direction.copy(e),this}copy(t){return this.origin.copy(t.origin),this.direction.copy(t.direction),this}at(t,e){return e.copy(this.origin).addScaledVector(this.direction,t)}lookAt(t){return this.direction.copy(t).sub(this.origin).normalize(),this}recast(t){return this.origin.copy(this.at(t,Oi)),this}closestPointToPoint(t,e){e.subVectors(t,this.origin);let n=e.dot(this.direction);return n<0?e.copy(this.origin):e.copy(this.origin).addScaledVector(this.direction,n)}distanceToPoint(t){return Math.sqrt(this.distanceSqToPoint(t))}distanceSqToPoint(t){let e=Oi.subVectors(t,this.origin).dot(this.direction);return e<0?this.origin.distanceToSquared(t):(Oi.copy(this.origin).addScaledVector(this.direction,e),Oi.distanceToSquared(t))}distanceSqToSegment(t,e,n,s){pc.copy(t).add(e).multiplyScalar(.5),Ya.copy(e).sub(t).normalize(),Za.copy(this.origin).sub(pc);let r=t.distanceTo(e)*.5,a=-this.direction.dot(Ya),o=Za.dot(this.direction),l=-Za.dot(Ya),c=Za.lengthSq(),h=Math.abs(1-a*a),p,d,f,_;if(h>0)if(p=a*l-o,d=a*o-l,_=r*h,p>=0)if(d>=-_)if(d<=_){let b=1/h;p*=b,d*=b,f=p*(p+a*d+2*o)+d*(a*p+d+2*l)+c}else d=r,p=Math.max(0,-(a*d+o)),f=-p*p+d*(d+2*l)+c;else d=-r,p=Math.max(0,-(a*d+o)),f=-p*p+d*(d+2*l)+c;else d<=-_?(p=Math.max(0,-(-a*r+o)),d=p>0?-r:Math.min(Math.max(-r,-l),r),f=-p*p+d*(d+2*l)+c):d<=_?(p=0,d=Math.min(Math.max(-r,-l),r),f=d*(d+2*l)+c):(p=Math.max(0,-(a*r+o)),d=p>0?r:Math.min(Math.max(-r,-l),r),f=-p*p+d*(d+2*l)+c);else d=a>0?-r:r,p=Math.max(0,-(a*d+o)),f=-p*p+d*(d+2*l)+c;return n&&n.copy(this.origin).addScaledVector(this.direction,p),s&&s.copy(pc).addScaledVector(Ya,d),f}intersectSphere(t,e){if(t.radius<0)return null;Oi.subVectors(t.center,this.origin);let n=Oi.dot(this.direction),s=Oi.dot(Oi)-n*n,r=t.radius*t.radius;if(s>r)return null;let a=Math.sqrt(r-s),o=n-a,l=n+a;return l<0?null:o<0?this.at(l,e):this.at(o,e)}intersectsSphere(t){return t.radius<0?!1:this.distanceSqToPoint(t.center)<=t.radius*t.radius}distanceToPlane(t){let e=t.normal.dot(this.direction);if(e===0)return t.distanceToPoint(this.origin)===0?0:null;let n=-(this.origin.dot(t.normal)+t.constant)/e;return n>=0?n:null}intersectPlane(t,e){let n=this.distanceToPlane(t);return n===null?null:this.at(n,e)}intersectsPlane(t){let e=t.distanceToPoint(this.origin);return e===0||t.normal.dot(this.direction)*e<0}intersectBox(t,e){let n,s,r,a,o,l,c=1/this.direction.x,h=1/this.direction.y,p=1/this.direction.z,d=this.origin;return c>=0?(n=(t.min.x-d.x)*c,s=(t.max.x-d.x)*c):(n=(t.max.x-d.x)*c,s=(t.min.x-d.x)*c),h>=0?(r=(t.min.y-d.y)*h,a=(t.max.y-d.y)*h):(r=(t.max.y-d.y)*h,a=(t.min.y-d.y)*h),n>a||r>s||((r>n||isNaN(n))&&(n=r),(a<s||isNaN(s))&&(s=a),p>=0?(o=(t.min.z-d.z)*p,l=(t.max.z-d.z)*p):(o=(t.max.z-d.z)*p,l=(t.min.z-d.z)*p),n>l||o>s)||((o>n||n!==n)&&(n=o),(l<s||s!==s)&&(s=l),s<0)?null:this.at(n>=0?n:s,e)}intersectsBox(t){return this.intersectBox(t,Oi)!==null}intersectTriangle(t,e,n,s,r){let a=this.origin,o=this.direction,l=o.x,c=o.y,h=o.z,p=t.x-a.x,d=t.y-a.y,f=t.z-a.z,_=e.x-a.x,b=e.y-a.y,m=e.z-a.z,u=n.x-a.x,S=n.y-a.y,R=n.z-a.z,v=Math.abs(l),M=Math.abs(c),E=Math.abs(h),A,g,w,T,I,N,B,F,P,V,z,X;if(v>=M&&v>=E?(w=l,N=p,P=_,X=u,l>=0?(A=c,g=h,T=d,I=f,B=b,F=m,V=S,z=R):(A=h,g=c,T=f,I=d,B=m,F=b,V=R,z=S)):M>=E?(w=c,N=d,P=b,X=S,c>=0?(A=h,g=l,T=f,I=p,B=m,F=_,V=R,z=u):(A=l,g=h,T=p,I=f,B=_,F=m,V=u,z=R)):(w=h,N=f,P=m,X=R,h>=0?(A=l,g=c,T=p,I=d,B=_,F=b,V=u,z=S):(A=c,g=l,T=d,I=p,B=b,F=_,V=S,z=u)),w===0)return null;let G=A/w,Y=g/w,tt=1/w,et=T-G*N,dt=I-Y*N,Dt=B-G*P,Pt=F-Y*P,xt=V-G*X,q=z-Y*X,it=xt*Pt-q*Dt,gt=et*q-dt*xt,zt=Dt*dt-Pt*et;if(s){if(it<0||gt<0||zt<0)return null}else if((it<0||gt<0||zt<0)&&(it>0||gt>0||zt>0))return null;let Rt=it+gt+zt;if(Rt===0)return null;let Yt=tt*(it*N+gt*P+zt*X);return(Rt>0?Yt<0:Yt>0)?null:this.at(Yt/Rt,r)}applyMatrix4(t){return this.origin.applyMatrix4(t),this.direction.transformDirection(t),this}equals(t){return t.origin.equals(this.origin)&&t.direction.equals(this.direction)}clone(){return new this.constructor().copy(this)}},Te=class extends os{constructor(t){super(),this.isMeshBasicMaterial=!0,this.type="MeshBasicMaterial",this.color=new jt(16777215),this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.specularMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new zn,this.combine=Dc,this.reflectivity=1,this.refractionRatio=.98,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.fog=!0,this.setValues(t)}copy(t){return super.copy(t),this.color.copy(t.color),this.map=t.map,this.lightMap=t.lightMap,this.lightMapIntensity=t.lightMapIntensity,this.aoMap=t.aoMap,this.aoMapIntensity=t.aoMapIntensity,this.specularMap=t.specularMap,this.alphaMap=t.alphaMap,this.envMap=t.envMap,this.envMapRotation.copy(t.envMapRotation),this.combine=t.combine,this.reflectivity=t.reflectivity,this.refractionRatio=t.refractionRatio,this.wireframe=t.wireframe,this.wireframeLinewidth=t.wireframeLinewidth,this.wireframeLinecap=t.wireframeLinecap,this.wireframeLinejoin=t.wireframeLinejoin,this.fog=t.fog,this}},Qh=new be,Ps=new zs,$a=new as,tu=new O,Ka=new O,Ja=new O,ja=new O,mc=new O,Qa=new O,eu=new O,to=new O,Xt=class extends dn{constructor(t=new fn,e=new Te){super(),this.isMesh=!0,this.type="Mesh",this.geometry=t,this.material=e,this.morphTargetDictionary=void 0,this.morphTargetInfluences=void 0,this.count=1,this.updateMorphTargets()}copy(t,e){return super.copy(t,e),t.morphTargetInfluences!==void 0&&(this.morphTargetInfluences=t.morphTargetInfluences.slice()),t.morphTargetDictionary!==void 0&&(this.morphTargetDictionary=Object.assign({},t.morphTargetDictionary)),this.material=Array.isArray(t.material)?t.material.slice():t.material,this.geometry=t.geometry,this}updateMorphTargets(){let e=this.geometry.morphAttributes,n=Object.keys(e);if(n.length>0){let s=e[n[0]];if(s!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let r=0,a=s.length;r<a;r++){let o=s[r].name||String(r);this.morphTargetInfluences.push(0),this.morphTargetDictionary[o]=r}}}}getVertexPosition(t,e){let n=this.geometry,s=n.attributes.position,r=n.morphAttributes.position,a=n.morphTargetsRelative;e.fromBufferAttribute(s,t);let o=this.morphTargetInfluences;if(r&&o){Qa.set(0,0,0);for(let l=0,c=r.length;l<c;l++){let h=o[l],p=r[l];h!==0&&(mc.fromBufferAttribute(p,t),a?Qa.addScaledVector(mc,h):Qa.addScaledVector(mc.sub(e),h))}e.add(Qa)}return e}intersectsFrustum(t){return t.intersectsObject(this)}raycast(t,e){let n=this.geometry,s=this.material,r=this.matrixWorld;s!==void 0&&(n.boundingSphere===null&&n.computeBoundingSphere(),$a.copy(n.boundingSphere),$a.applyMatrix4(r),Ps.copy(t.ray).recast(t.near),!($a.containsPoint(Ps.origin)===!1&&(Ps.intersectSphere($a,tu)===null||Ps.origin.distanceToSquared(tu)>(t.far-t.near)**2))&&(Qh.copy(r).invert(),Ps.copy(t.ray).applyMatrix4(Qh),!(n.boundingBox!==null&&Ps.intersectsBox(n.boundingBox)===!1)&&this._computeIntersections(t,e,Ps)))}_computeIntersections(t,e,n){let s,r=this.geometry,a=this.material,o=r.index,l=r.attributes.position,c=r.attributes.uv,h=r.attributes.uv1,p=r.attributes.normal,d=r.groups,f=r.drawRange;if(o!==null)if(Array.isArray(a))for(let _=0,b=d.length;_<b;_++){let m=d[_],u=a[m.materialIndex],S=Math.max(m.start,f.start),R=Math.min(o.count,Math.min(m.start+m.count,f.start+f.count));for(let v=S,M=R;v<M;v+=3){let E=o.getX(v),A=o.getX(v+1),g=o.getX(v+2);s=eo(this,u,t,n,c,h,p,E,A,g),s&&(s.faceIndex=Math.floor(v/3),s.face.materialIndex=m.materialIndex,e.push(s))}}else{let _=Math.max(0,f.start),b=Math.min(o.count,f.start+f.count);for(let m=_,u=b;m<u;m+=3){let S=o.getX(m),R=o.getX(m+1),v=o.getX(m+2);s=eo(this,a,t,n,c,h,p,S,R,v),s&&(s.faceIndex=Math.floor(m/3),e.push(s))}}else if(l!==void 0)if(Array.isArray(a))for(let _=0,b=d.length;_<b;_++){let m=d[_],u=a[m.materialIndex],S=Math.max(m.start,f.start),R=Math.min(l.count,Math.min(m.start+m.count,f.start+f.count));for(let v=S,M=R;v<M;v+=3){let E=v,A=v+1,g=v+2;s=eo(this,u,t,n,c,h,p,E,A,g),s&&(s.faceIndex=Math.floor(v/3),s.face.materialIndex=m.materialIndex,e.push(s))}}else{let _=Math.max(0,f.start),b=Math.min(l.count,f.start+f.count);for(let m=_,u=b;m<u;m+=3){let S=m,R=m+1,v=m+2;s=eo(this,a,t,n,c,h,p,S,R,v),s&&(s.faceIndex=Math.floor(m/3),e.push(s))}}}};function Zf(i,t,e,n,s,r,a,o){let l;if(t.side===bn?l=n.intersectTriangle(a,r,s,!0,o):l=n.intersectTriangle(s,r,a,t.side===ps,o),l===null)return null;to.copy(o),to.applyMatrix4(i.matrixWorld);let c=e.ray.origin.distanceTo(to);return c<e.near||c>e.far?null:{distance:c,point:to.clone(),object:i}}function eo(i,t,e,n,s,r,a,o,l,c){i.getVertexPosition(o,Ka),i.getVertexPosition(l,Ja),i.getVertexPosition(c,ja);let h=Zf(i,t,e,n,Ka,Ja,ja,eu);if(h){let p=new O;rs.getBarycoord(eu,Ka,Ja,ja,p),s&&(h.uv=rs.getInterpolatedAttribute(s,o,l,c,p,new qt)),r&&(h.uv1=rs.getInterpolatedAttribute(r,o,l,c,p,new qt)),a&&(h.normal=rs.getInterpolatedAttribute(a,o,l,c,p,new O),h.normal.dot(n.direction)>0&&h.normal.multiplyScalar(-1));let d={a:o,b:l,c,normal:new O,materialIndex:0};rs.getNormal(Ka,Ja,ja,d.normal),h.face=d,h.barycoord=p}return h}var ca=class extends vn{constructor(t=null,e=1,n=1,s,r,a,o,l,c=tn,h=tn,p,d){super(null,a,o,l,c,h,s,r,p,d),this.isDataTexture=!0,this.image={data:t,width:e,height:n},this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}};var vr=class extends on{constructor(t,e,n,s=1){super(t,e,n),this.isInstancedBufferAttribute=!0,this.meshPerAttribute=s}copy(t){return super.copy(t),this.meshPerAttribute=t.meshPerAttribute,this}toJSON(){let t=super.toJSON();return t.meshPerAttribute=this.meshPerAttribute,t.isInstancedBufferAttribute=!0,t}},or=new be,nu=new be,no=[],iu=new _i,$f=new be,jr=new Xt,Qr=new as,ki=class extends Xt{constructor(t,e,n){super(t,e),this.isInstancedMesh=!0,this.instanceMatrix=new vr(new Float32Array(n*16),16),this.instanceColor=null,this.morphTexture=null,this.count=n,this.boundingBox=null,this.boundingSphere=null;for(let s=0;s<n;s++)this.setMatrixAt(s,$f)}computeBoundingBox(){let t=this.geometry,e=this.count;this.boundingBox===null&&(this.boundingBox=new _i),t.boundingBox===null&&t.computeBoundingBox(),this.boundingBox.makeEmpty();for(let n=0;n<e;n++)this.getMatrixAt(n,or),iu.copy(t.boundingBox).applyMatrix4(or),this.boundingBox.union(iu)}computeBoundingSphere(){let t=this.geometry,e=this.count;this.boundingSphere===null&&(this.boundingSphere=new as),t.boundingSphere===null&&t.computeBoundingSphere(),this.boundingSphere.makeEmpty();for(let n=0;n<e;n++)this.getMatrixAt(n,or),Qr.copy(t.boundingSphere).applyMatrix4(or),this.boundingSphere.union(Qr)}copy(t,e){return super.copy(t,e),this.instanceMatrix.copy(t.instanceMatrix),t.morphTexture!==null&&(this.morphTexture=t.morphTexture.clone()),t.instanceColor!==null&&(this.instanceColor=t.instanceColor.clone()),this.count=t.count,t.boundingBox!==null&&(this.boundingBox=t.boundingBox.clone()),t.boundingSphere!==null&&(this.boundingSphere=t.boundingSphere.clone()),this}getColorAt(t,e){return this.instanceColor===null?e.setRGB(1,1,1):e.fromArray(this.instanceColor.array,t*3)}getMatrixAt(t,e){return e.fromArray(this.instanceMatrix.array,t*16)}getMorphAt(t,e){let n=e.morphTargetInfluences,s=this.morphTexture.source.data.data,r=n.length+1,a=t*r+1;for(let o=0;o<n.length;o++)n[o]=s[a+o]}raycast(t,e){let n=this.matrixWorld,s=this.count;if(jr.geometry=this.geometry,jr.material=this.material,jr.material!==void 0&&(this.boundingSphere===null&&this.computeBoundingSphere(),Qr.copy(this.boundingSphere),Qr.applyMatrix4(n),t.ray.intersectsSphere(Qr)!==!1))for(let r=0;r<s;r++){this.getMatrixAt(r,or),nu.multiplyMatrices(n,or),jr.matrixWorld=nu,jr.raycast(t,no);for(let a=0,o=no.length;a<o;a++){let l=no[a];l.instanceId=r,l.object=this,e.push(l)}no.length=0}}setColorAt(t,e){return this.instanceColor===null&&(this.instanceColor=new vr(new Float32Array(this.instanceMatrix.count*3).fill(1),3)),e.toArray(this.instanceColor.array,t*3),this}setMatrixAt(t,e){return e.toArray(this.instanceMatrix.array,t*16),this}setMorphAt(t,e){let n=e.morphTargetInfluences,s=n.length+1;this.morphTexture===null&&(this.morphTexture=new ca(new Float32Array(s*this.count),s,this.count,Xo,Vn));let r=this.morphTexture.source.data.data,a=0;for(let c=0;c<n.length;c++)a+=n[c];let o=this.geometry.morphTargetsRelative?1:1-a,l=s*t;return r[l]=o,r.set(n,l+1),this}updateMorphTargets(){}dispose(){super.dispose(),this.morphTexture!==null&&(this.morphTexture.dispose(),this.morphTexture=null)}},Is=new as,Kf=new qt(.5,.5),io=new O,br=class{constructor(t=new Dn,e=new Dn,n=new Dn,s=new Dn,r=new Dn,a=new Dn){this.planes=[t,e,n,s,r,a]}set(t,e,n,s,r,a){let o=this.planes;return o[0].copy(t),o[1].copy(e),o[2].copy(n),o[3].copy(s),o[4].copy(r),o[5].copy(a),this}copy(t){let e=this.planes;for(let n=0;n<6;n++)e[n].copy(t.planes[n]);return this}setFromProjectionMatrix(t,e=ni,n=!1){let s=this.planes,r=t.elements,a=r[0],o=r[1],l=r[2],c=r[3],h=r[4],p=r[5],d=r[6],f=r[7],_=r[8],b=r[9],m=r[10],u=r[11],S=r[12],R=r[13],v=r[14],M=r[15];if(s[0].setComponents(c-a,f-h,u-_,M-S).normalize(),s[1].setComponents(c+a,f+h,u+_,M+S).normalize(),s[2].setComponents(c+o,f+p,u+b,M+R).normalize(),s[3].setComponents(c-o,f-p,u-b,M-R).normalize(),n)s[4].setComponents(l,d,m,v).normalize(),s[5].setComponents(c-l,f-d,u-m,M-v).normalize();else if(s[4].setComponents(c-l,f-d,u-m,M-v).normalize(),e===ni)s[5].setComponents(c+l,f+d,u+m,M+v).normalize();else if(e===pr)s[5].setComponents(l,d,m,v).normalize();else throw new Error("THREE.Frustum.setFromProjectionMatrix(): Invalid coordinate system: "+e);return this}intersectsObject(t){if(t.boundingSphere!==void 0)t.boundingSphere===null&&t.computeBoundingSphere(),Is.copy(t.boundingSphere).applyMatrix4(t.matrixWorld);else{let e=t.geometry;e.boundingSphere===null&&e.computeBoundingSphere(),Is.copy(e.boundingSphere).applyMatrix4(t.matrixWorld)}return this.intersectsSphere(Is)}intersectsSprite(t){Is.center.set(0,0,0);let e=Kf.distanceTo(t.center);return Is.radius=.7071067811865476+e,Is.applyMatrix4(t.matrixWorld),this.intersectsSphere(Is)}intersectsSphere(t){let e=this.planes,n=t.center,s=-t.radius;for(let r=0;r<6;r++)if(e[r].distanceToPoint(n)<s)return!1;return!0}intersectsBox(t){let e=this.planes;for(let n=0;n<6;n++){let s=e[n];if(io.x=s.normal.x>0?t.max.x:t.min.x,io.y=s.normal.y>0?t.max.y:t.min.y,io.z=s.normal.z>0?t.max.z:t.min.z,s.distanceToPoint(io)<0)return!1}return!0}containsPoint(t){let e=this.planes;for(let n=0;n<6;n++)if(e[n].distanceToPoint(t)<0)return!1;return!0}clone(){return new this.constructor().copy(this)}};var ha=class extends vn{constructor(t=[],e=ms,n,s,r,a,o,l,c,h){super(t,e,n,s,r,a,o,l,c,h),this.isCubeTexture=!0,this.flipY=!1}get images(){return this.image}set images(t){this.image=t}},Hi=class extends vn{constructor(t,e,n,s,r,a,o,l,c){super(t,e,n,s,r,a,o,l,c),this.isCanvasTexture=!0,this.needsUpdate=!0}};var ls=class extends vn{constructor(t,e,n=ri,s,r,a,o=tn,l=tn,c,h=xi,p=1){if(h!==xi&&h!==xs)throw new Error("THREE.DepthTexture: format must be either THREE.DepthFormat or THREE.DepthStencilFormat");let d={width:t,height:e,depth:p};super(d,s,r,a,o,l,h,n,c),this.isDepthTexture=!0,this.flipY=!1,this.generateMipmaps=!1,this.compareFunction=null}copy(t){return super.copy(t),this.source=new xr(Object.assign({},t.image)),this.compareFunction=t.compareFunction,this}toJSON(t){let e=super.toJSON(t);return e.compareFunction=this.compareFunction,e}},bo=class extends ls{constructor(t,e=ri,n=ms,s,r,a=tn,o=tn,l,c=xi){let h={width:t,height:t,depth:1},p=[h,h,h,h,h,h];super(t,t,e,n,s,r,a,o,l,c),this.image=p,this.isCubeDepthTexture=!0,this.isCubeTexture=!0}get images(){return this.image}set images(t){this.image=t}},ua=class extends vn{constructor(t=null){super(),this.sourceTexture=t,this.isExternalTexture=!0}copy(t){return super.copy(t),this.sourceTexture=t.sourceTexture,this}},de=class i extends fn{constructor(t=1,e=1,n=1,s=1,r=1,a=1){super(),this.type="BoxGeometry",this.parameters={width:t,height:e,depth:n,widthSegments:s,heightSegments:r,depthSegments:a};let o=this;s=Math.floor(s),r=Math.floor(r),a=Math.floor(a);let l=[],c=[],h=[],p=[],d=0,f=0;_("z","y","x",-1,-1,n,e,t,a,r,0),_("z","y","x",1,-1,n,e,-t,a,r,1),_("x","z","y",1,1,t,n,e,s,a,2),_("x","z","y",1,-1,t,n,-e,s,a,3),_("x","y","z",1,-1,t,e,n,s,r,4),_("x","y","z",-1,-1,t,e,-n,s,r,5),this.setIndex(l),this.setAttribute("position",new Fe(c,3)),this.setAttribute("normal",new Fe(h,3)),this.setAttribute("uv",new Fe(p,2));function _(b,m,u,S,R,v,M,E,A,g,w){let T=v/A,I=M/g,N=v/2,B=M/2,F=E/2,P=A+1,V=g+1,z=0,X=0,G=new O;for(let Y=0;Y<V;Y++){let tt=Y*I-B;for(let et=0;et<P;et++){let dt=et*T-N;G[b]=dt*S,G[m]=tt*R,G[u]=F,c.push(G.x,G.y,G.z),G[b]=0,G[m]=0,G[u]=E>0?1:-1,h.push(G.x,G.y,G.z),p.push(et/A),p.push(1-Y/g),z+=1}}for(let Y=0;Y<g;Y++)for(let tt=0;tt<A;tt++){let et=d+tt+P*Y,dt=d+tt+P*(Y+1),Dt=d+(tt+1)+P*(Y+1),Pt=d+(tt+1)+P*Y;l.push(et,dt,Pt),l.push(dt,Dt,Pt),X+=6}o.addGroup(f,X,w),f+=X,d+=z}}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.width,t.height,t.depth,t.widthSegments,t.heightSegments,t.depthSegments)}};var Mr=class i extends fn{constructor(t=1,e=1,n=1,s=32,r=1,a=!1,o=0,l=Math.PI*2){super(),this.type="CylinderGeometry",this.parameters={radiusTop:t,radiusBottom:e,height:n,radialSegments:s,heightSegments:r,openEnded:a,thetaStart:o,thetaLength:l};let c=this;s=Math.floor(s),r=Math.floor(r);let h=[],p=[],d=[],f=[],_=0,b=[],m=n/2,u=0;S(),a===!1&&(t>0&&R(!0),e>0&&R(!1)),this.setIndex(h),this.setAttribute("position",new Fe(p,3)),this.setAttribute("normal",new Fe(d,3)),this.setAttribute("uv",new Fe(f,2));function S(){let v=new O,M=new O,E=0,A=(e-t)/n;for(let g=0;g<=r;g++){let w=[],T=g/r,I=T*(e-t)+t;for(let N=0;N<=s;N++){let B=N/s,F=B*l+o,P=Math.sin(F),V=Math.cos(F);M.x=I*P,M.y=-T*n+m,M.z=I*V,p.push(M.x,M.y,M.z),v.set(P,A,V).normalize(),d.push(v.x,v.y,v.z),f.push(B,1-T),w.push(_++)}b.push(w)}for(let g=0;g<s;g++)for(let w=0;w<r;w++){let T=b[w][g],I=b[w+1][g],N=b[w+1][g+1],B=b[w][g+1];(t>0||w!==0)&&(h.push(T,I,B),E+=3),(e>0||w!==r-1)&&(h.push(I,N,B),E+=3)}c.addGroup(u,E,0),u+=E}function R(v){let M=_,E=new qt,A=new O,g=0,w=v===!0?t:e,T=v===!0?1:-1;for(let N=1;N<=s;N++)p.push(0,m*T,0),d.push(0,T,0),f.push(.5,.5),_++;let I=_;for(let N=0;N<=s;N++){let F=N/s*l+o,P=Math.cos(F),V=Math.sin(F);A.x=w*V,A.y=m*T,A.z=w*P,p.push(A.x,A.y,A.z),d.push(0,T,0),E.x=P*.5+.5,E.y=V*.5*T+.5,f.push(E.x,E.y),_++}for(let N=0;N<s;N++){let B=M+N,F=I+N;v===!0?h.push(F,F+1,B):h.push(F+1,F,B),g+=3}c.addGroup(u,g,v===!0?1:2),u+=g}}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.radiusTop,t.radiusBottom,t.height,t.radialSegments,t.heightSegments,t.openEnded,t.thetaStart,t.thetaLength)}},da=class i extends Mr{constructor(t=1,e=1,n=32,s=1,r=!1,a=0,o=Math.PI*2){super(0,t,e,n,s,r,a,o),this.type="ConeGeometry",this.parameters={radius:t,height:e,radialSegments:n,heightSegments:s,openEnded:r,thetaStart:a,thetaLength:o}}static fromJSON(t){return new i(t.radius,t.height,t.radialSegments,t.heightSegments,t.openEnded,t.thetaStart,t.thetaLength)}},Mo=class i extends fn{constructor(t=[],e=[],n=1,s=0){super(),this.type="PolyhedronGeometry",this.parameters={vertices:t,indices:e,radius:n,detail:s};let r=[],a=[];o(s),c(n),h(),this.setAttribute("position",new Fe(r,3)),this.setAttribute("normal",new Fe(r.slice(),3)),this.setAttribute("uv",new Fe(a,2)),s===0?this.computeVertexNormals():this.normalizeNormals();function o(S){let R=new O,v=new O,M=new O;for(let E=0;E<e.length;E+=3)f(e[E+0],R),f(e[E+1],v),f(e[E+2],M),l(R,v,M,S)}function l(S,R,v,M){let E=M+1,A=[];for(let g=0;g<=E;g++){A[g]=[];let w=S.clone().lerp(v,g/E),T=R.clone().lerp(v,g/E),I=E-g;for(let N=0;N<=I;N++)N===0&&g===E?A[g][N]=w:A[g][N]=w.clone().lerp(T,N/I)}for(let g=0;g<E;g++)for(let w=0;w<2*(E-g)-1;w++){let T=Math.floor(w/2);w%2===0?(d(A[g][T+1]),d(A[g+1][T]),d(A[g][T])):(d(A[g][T+1]),d(A[g+1][T+1]),d(A[g+1][T]))}}function c(S){let R=new O;for(let v=0;v<r.length;v+=3)R.x=r[v+0],R.y=r[v+1],R.z=r[v+2],R.normalize().multiplyScalar(S),r[v+0]=R.x,r[v+1]=R.y,r[v+2]=R.z}function h(){let S=new O;for(let R=0;R<r.length;R+=3){S.x=r[R+0],S.y=r[R+1],S.z=r[R+2];let v=m(S)/2/Math.PI+.5,M=u(S)/Math.PI+.5;a.push(v,1-M)}_(),p()}function p(){for(let S=0;S<a.length;S+=6){let R=a[S+0],v=a[S+2],M=a[S+4],E=Math.max(R,v,M),A=Math.min(R,v,M);E>.9&&A<.1&&(R<.2&&(a[S+0]+=1),v<.2&&(a[S+2]+=1),M<.2&&(a[S+4]+=1))}}function d(S){r.push(S.x,S.y,S.z)}function f(S,R){let v=S*3;R.x=t[v+0],R.y=t[v+1],R.z=t[v+2]}function _(){let S=new O,R=new O,v=new O,M=new O,E=new qt,A=new qt,g=new qt;for(let w=0,T=0;w<r.length;w+=9,T+=6){S.set(r[w+0],r[w+1],r[w+2]),R.set(r[w+3],r[w+4],r[w+5]),v.set(r[w+6],r[w+7],r[w+8]),E.set(a[T+0],a[T+1]),A.set(a[T+2],a[T+3]),g.set(a[T+4],a[T+5]),M.copy(S).add(R).add(v).divideScalar(3);let I=m(M);b(E,T+0,S,I),b(A,T+2,R,I),b(g,T+4,v,I)}}function b(S,R,v,M){M<0&&S.x===1&&(a[R]=S.x-1),v.x===0&&v.z===0&&(a[R]=M/2/Math.PI+.5)}function m(S){return Math.atan2(S.z,-S.x)}function u(S){return Math.atan2(-S.y,Math.sqrt(S.x*S.x+S.z*S.z))}}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.vertices,t.indices,t.radius,t.detail)}},fa=class i extends Mo{constructor(t=1,e=0){let n=(1+Math.sqrt(5))/2,s=1/n,r=[-1,-1,-1,-1,-1,1,-1,1,-1,-1,1,1,1,-1,-1,1,-1,1,1,1,-1,1,1,1,0,-s,-n,0,-s,n,0,s,-n,0,s,n,-s,-n,0,-s,n,0,s,-n,0,s,n,0,-n,0,-s,n,0,-s,-n,0,s,n,0,s],a=[3,11,7,3,7,15,3,15,13,7,19,17,7,17,6,7,6,15,17,4,8,17,8,10,17,10,6,8,0,16,8,16,2,8,2,10,0,12,1,0,1,18,0,18,16,6,10,2,6,2,13,6,13,15,2,16,18,2,18,3,2,3,13,18,1,9,18,9,11,18,11,3,4,14,12,4,12,0,4,0,8,11,9,5,11,5,19,11,19,7,19,5,14,19,14,4,19,4,17,1,12,14,1,14,5,1,5,9];super(r,a,t,e),this.type="DodecahedronGeometry",this.parameters={radius:t,detail:e}}static fromJSON(t){return new i(t.radius,t.detail)}};var Ns=class i extends fn{constructor(t=1,e=1,n=1,s=1){super(),this.type="PlaneGeometry",this.parameters={width:t,height:e,widthSegments:n,heightSegments:s};let r=t/2,a=e/2,o=Math.floor(n),l=Math.floor(s),c=o+1,h=l+1,p=t/o,d=e/l,f=[],_=[],b=[],m=[];for(let u=0;u<h;u++){let S=u*d-a;for(let R=0;R<c;R++){let v=R*p-r;_.push(v,-S,0),b.push(0,0,1),m.push(R/o),m.push(1-u/l)}}for(let u=0;u<l;u++)for(let S=0;S<o;S++){let R=S+c*u,v=S+c*(u+1),M=S+1+c*(u+1),E=S+1+c*u;f.push(R,v,E),f.push(v,M,E)}this.setIndex(f),this.setAttribute("position",new Fe(_,3)),this.setAttribute("normal",new Fe(b,3)),this.setAttribute("uv",new Fe(m,2))}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.width,t.height,t.widthSegments,t.heightSegments)}};var pa=class i extends fn{constructor(t=1,e=32,n=16,s=0,r=Math.PI*2,a=0,o=Math.PI){super(),this.type="SphereGeometry",this.parameters={radius:t,widthSegments:e,heightSegments:n,phiStart:s,phiLength:r,thetaStart:a,thetaLength:o},e=Math.max(3,Math.floor(e)),n=Math.max(2,Math.floor(n));let l=Math.min(a+o,Math.PI),c=0,h=[],p=new O,d=new O,f=[],_=[],b=[],m=[];for(let u=0;u<=n;u++){let S=[],R=u/n,v=a+R*o,M=t*Math.cos(v),E=Math.sqrt(t*t-M*M),A=0;u===0&&a===0?A=.5/e:u===n&&l===Math.PI&&(A=-.5/e);for(let g=0;g<=e;g++){let w=g/e,T=s+w*r;p.x=-E*Math.cos(T),p.y=M,p.z=E*Math.sin(T),_.push(p.x,p.y,p.z),d.copy(p).normalize(),b.push(d.x,d.y,d.z),m.push(w+A,1-R),S.push(c++)}h.push(S)}for(let u=0;u<n;u++)for(let S=0;S<e;S++){let R=h[u][S+1],v=h[u][S],M=h[u+1][S],E=h[u+1][S+1];(u!==0||a>0)&&f.push(R,v,E),(u!==n-1||l<Math.PI)&&f.push(v,M,E)}this.setIndex(f),this.setAttribute("position",new Fe(_,3)),this.setAttribute("normal",new Fe(b,3)),this.setAttribute("uv",new Fe(m,2))}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.radius,t.widthSegments,t.heightSegments,t.phiStart,t.phiLength,t.thetaStart,t.thetaLength)}};var ma=class i extends fn{constructor(t=1,e=.4,n=12,s=48,r=Math.PI*2,a=0,o=Math.PI*2){super(),this.type="TorusGeometry",this.parameters={radius:t,tube:e,radialSegments:n,tubularSegments:s,arc:r,thetaStart:a,thetaLength:o},n=Math.floor(n),s=Math.floor(s);let l=[],c=[],h=[],p=[],d=new O,f=new O,_=new O;for(let b=0;b<=n;b++){let m=a+b/n*o;for(let u=0;u<=s;u++){let S=u/s*r;f.x=(t+e*Math.cos(m))*Math.cos(S),f.y=(t+e*Math.cos(m))*Math.sin(S),f.z=e*Math.sin(m),c.push(f.x,f.y,f.z),d.x=t*Math.cos(S),d.y=t*Math.sin(S),_.subVectors(f,d).normalize(),h.push(_.x,_.y,_.z),p.push(u/s),p.push(b/n)}}for(let b=1;b<=n;b++)for(let m=1;m<=s;m++){let u=(s+1)*b+m-1,S=(s+1)*(b-1)+m-1,R=(s+1)*(b-1)+m,v=(s+1)*b+m;l.push(u,S,v),l.push(S,R,v)}this.setIndex(l),this.setAttribute("position",new Fe(c,3)),this.setAttribute("normal",new Fe(h,3)),this.setAttribute("uv",new Fe(p,2))}copy(t){return super.copy(t),this.parameters=Object.assign({},t.parameters),this}static fromJSON(t){return new i(t.radius,t.tube,t.radialSegments,t.tubularSegments,t.arc,t.thetaStart,t.thetaLength)}};function Hs(i){let t={};for(let e in i){t[e]={};for(let n in i[e]){let s=i[e][n];if(su(s))s.isRenderTargetTexture?(Zt("UniformsUtils: Textures of render targets cannot be cloned via cloneUniforms() or mergeUniforms()."),t[e][n]=null):t[e][n]=s.clone();else if(Array.isArray(s))if(su(s[0])){let r=[];for(let a=0,o=s.length;a<o;a++)r[a]=s[a].clone();t[e][n]=r}else t[e][n]=s.slice();else t[e][n]=s}}return t}function pn(i){let t={};for(let e=0;e<i.length;e++){let n=Hs(i[e]);for(let s in n)t[s]=n[s]}return t}function su(i){return i&&(i.isColor||i.isMatrix3||i.isMatrix4||i.isVector2||i.isVector3||i.isVector4||i.isTexture||i.isQuaternion)}function Jf(i){let t=[];for(let e=0;e<i.length;e++)t.push(i[e].clone());return t}function Kc(i){let t=i.getRenderTarget();return t===null?i.outputColorSpace:t.isXRRenderTarget===!0?t.texture.colorSpace:me.workingColorSpace}var Ju={clone:Hs,merge:pn},jf=`void main() {
	gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}`,Qf=`void main() {
	gl_FragColor = vec4( 1.0, 0.0, 0.0, 1.0 );
}`,Nn=class extends os{constructor(t){super(),this.isShaderMaterial=!0,this.type="ShaderMaterial",this.defines={},this.uniforms={},this.uniformsGroups=[],this.vertexShader=jf,this.fragmentShader=Qf,this.linewidth=1,this.wireframe=!1,this.wireframeLinewidth=1,this.fog=!1,this.lights=!1,this.clipping=!1,this.forceSinglePass=!0,this.extensions={clipCullDistance:!1,multiDraw:!1},this.defaultAttributeValues={color:[1,1,1],uv:[0,0],uv1:[0,0]},this.index0AttributeName=void 0,this.uniformsNeedUpdate=!1,this.glslVersion=null,t!==void 0&&this.setValues(t)}copy(t){return super.copy(t),this.fragmentShader=t.fragmentShader,this.vertexShader=t.vertexShader,this.uniforms=Hs(t.uniforms),this.uniformsGroups=Jf(t.uniformsGroups),this.defines=Object.assign({},t.defines),this.wireframe=t.wireframe,this.wireframeLinewidth=t.wireframeLinewidth,this.fog=t.fog,this.lights=t.lights,this.clipping=t.clipping,this.extensions=Object.assign({},t.extensions),this.glslVersion=t.glslVersion,this.defaultAttributeValues=Object.assign({},t.defaultAttributeValues),this.index0AttributeName=t.index0AttributeName,this.uniformsNeedUpdate=t.uniformsNeedUpdate,this}toJSON(t){let e=super.toJSON(t);e.glslVersion=this.glslVersion,e.uniforms={};for(let s in this.uniforms){let a=this.uniforms[s].value;a&&a.isTexture?e.uniforms[s]={type:"t",value:a.toJSON(t).uuid}:a&&a.isColor?e.uniforms[s]={type:"c",value:a.getHex()}:a&&a.isVector2?e.uniforms[s]={type:"v2",value:a.toArray()}:a&&a.isVector3?e.uniforms[s]={type:"v3",value:a.toArray()}:a&&a.isVector4?e.uniforms[s]={type:"v4",value:a.toArray()}:a&&a.isMatrix3?e.uniforms[s]={type:"m3",value:a.toArray()}:a&&a.isMatrix4?e.uniforms[s]={type:"m4",value:a.toArray()}:e.uniforms[s]={value:a}}Object.keys(this.defines).length>0&&(e.defines=this.defines),e.vertexShader=this.vertexShader,e.fragmentShader=this.fragmentShader,e.lights=this.lights,e.clipping=this.clipping;let n={};for(let s in this.extensions)this.extensions[s]===!0&&(n[s]=!0);return Object.keys(n).length>0&&(e.extensions=n),e}fromJSON(t,e){if(super.fromJSON(t,e),t.uniforms!==void 0)for(let n in t.uniforms){let s=t.uniforms[n];switch(this.uniforms[n]={},s.type){case"t":this.uniforms[n].value=e[s.value]||null;break;case"c":this.uniforms[n].value=new jt().setHex(s.value);break;case"v2":this.uniforms[n].value=new qt().fromArray(s.value);break;case"v3":this.uniforms[n].value=new O().fromArray(s.value);break;case"v4":this.uniforms[n].value=new Oe().fromArray(s.value);break;case"m3":this.uniforms[n].value=new ee().fromArray(s.value);break;case"m4":this.uniforms[n].value=new be().fromArray(s.value);break;default:this.uniforms[n].value=s.value}}if(t.defines!==void 0&&(this.defines=t.defines),t.vertexShader!==void 0&&(this.vertexShader=t.vertexShader),t.fragmentShader!==void 0&&(this.fragmentShader=t.fragmentShader),t.glslVersion!==void 0&&(this.glslVersion=t.glslVersion),t.extensions!==void 0)for(let n in t.extensions)this.extensions[n]=t.extensions[n];return t.lights!==void 0&&(this.lights=t.lights),t.clipping!==void 0&&(this.clipping=t.clipping),this}},So=class extends Nn{constructor(t){super(t),this.isRawShaderMaterial=!0,this.type="RawShaderMaterial"}},Ae=class extends os{constructor(t){super(),this.isMeshStandardMaterial=!0,this.type="MeshStandardMaterial",this.defines={STANDARD:""},this.color=new jt(16777215),this.roughness=1,this.metalness=0,this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.emissive=new jt(0),this.emissiveIntensity=1,this.emissiveMap=null,this.bumpMap=null,this.bumpScale=1,this.normalMap=null,this.normalMapType=wl,this.normalScale=new qt(1,1),this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.roughnessMap=null,this.metalnessMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new zn,this.envMapIntensity=1,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.flatShading=!1,this.fog=!0,this.setValues(t)}copy(t){return super.copy(t),this.defines={STANDARD:""},this.color.copy(t.color),this.roughness=t.roughness,this.metalness=t.metalness,this.map=t.map,this.lightMap=t.lightMap,this.lightMapIntensity=t.lightMapIntensity,this.aoMap=t.aoMap,this.aoMapIntensity=t.aoMapIntensity,this.emissive.copy(t.emissive),this.emissiveMap=t.emissiveMap,this.emissiveIntensity=t.emissiveIntensity,this.bumpMap=t.bumpMap,this.bumpScale=t.bumpScale,this.normalMap=t.normalMap,this.normalMapType=t.normalMapType,this.normalScale.copy(t.normalScale),this.displacementMap=t.displacementMap,this.displacementScale=t.displacementScale,this.displacementBias=t.displacementBias,this.roughnessMap=t.roughnessMap,this.metalnessMap=t.metalnessMap,this.alphaMap=t.alphaMap,this.envMap=t.envMap,this.envMapRotation.copy(t.envMapRotation),this.envMapIntensity=t.envMapIntensity,this.wireframe=t.wireframe,this.wireframeLinewidth=t.wireframeLinewidth,this.wireframeLinecap=t.wireframeLinecap,this.wireframeLinejoin=t.wireframeLinejoin,this.flatShading=t.flatShading,this.fog=t.fog,this}};var Eo=class extends os{constructor(t){super(),this.isMeshDepthMaterial=!0,this.type="MeshDepthMaterial",this.depthPacking=Uu,this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.wireframe=!1,this.wireframeLinewidth=1,this.setValues(t)}copy(t){return super.copy(t),this.depthPacking=t.depthPacking,this.map=t.map,this.alphaMap=t.alphaMap,this.displacementMap=t.displacementMap,this.displacementScale=t.displacementScale,this.displacementBias=t.displacementBias,this.wireframe=t.wireframe,this.wireframeLinewidth=t.wireframeLinewidth,this}},wo=class extends os{constructor(t){super(),this.isMeshDistanceMaterial=!0,this.type="MeshDistanceMaterial",this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.setValues(t)}copy(t){return super.copy(t),this.map=t.map,this.alphaMap=t.alphaMap,this.displacementMap=t.displacementMap,this.displacementScale=t.displacementScale,this.displacementBias=t.displacementBias,this}};function lr(i,t){return!i||i.constructor===t?i:typeof t.BYTES_PER_ELEMENT=="number"?new t(i):Array.prototype.slice.call(i)}function gc(i){return i!==void 0&&i.inTangents!==void 0&&i.outTangents!==void 0}var cs=class{constructor(t,e,n,s){this.parameterPositions=t,this._cachedIndex=0,this.resultBuffer=s!==void 0?s:new e.constructor(n),this.sampleValues=e,this.valueSize=n,this.settings=null,this.DefaultSettings_={}}evaluate(t){let e=this.parameterPositions,n=this._cachedIndex,s=e[n],r=e[n-1];n:{t:{let a;e:{i:if(!(t<s)){for(let o=n+2;;){if(s===void 0){if(t<r)break i;return n=e.length,this._cachedIndex=n,this.copySampleValue_(n-1)}if(n===o)break;if(r=s,s=e[++n],t<s)break t}a=e.length;break e}if(!(t>=r)){let o=e[1];t<o&&(n=2,r=o);for(let l=n-2;;){if(r===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(n===l)break;if(s=r,r=e[--n-1],t>=r)break t}a=n,n=0;break e}break n}for(;n<a;){let o=n+a>>>1;t<e[o]?a=o:n=o+1}if(s=e[n],r=e[n-1],r===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(s===void 0)return n=e.length,this._cachedIndex=n,this.copySampleValue_(n-1)}this._cachedIndex=n,this.intervalChanged_(n,r,s)}return this.interpolate_(n,r,t,s)}getSettings_(){return this.settings||this.DefaultSettings_}copySampleValue_(t){let e=this.resultBuffer,n=this.sampleValues,s=this.valueSize,r=t*s;for(let a=0;a!==s;++a)e[a]=n[r+a];return e}interpolate_(){throw new Error("THREE.Interpolant: Call to abstract method.")}intervalChanged_(){}},To=class extends cs{constructor(t,e,n,s){super(t,e,n,s),this._weightPrev=-0,this._offsetPrev=-0,this._weightNext=-0,this._offsetNext=-0,this.DefaultSettings_={endingStart:yc,endingEnd:yc}}intervalChanged_(t,e,n){let s=this.parameterPositions,r=t-2,a=t+1,o=s[r],l=s[a];if(o===void 0)switch(this.getSettings_().endingStart){case vc:r=t,o=2*e-n;break;case bc:r=s.length-2,o=e+s[r]-s[r+1];break;default:r=t,o=n}if(l===void 0)switch(this.getSettings_().endingEnd){case vc:a=t,l=2*n-e;break;case bc:a=1,l=n+s[1]-s[0];break;default:a=t-1,l=e}let c=(n-e)*.5,h=this.valueSize;this._weightPrev=c/(e-o),this._weightNext=c/(l-n),this._offsetPrev=r*h,this._offsetNext=a*h}interpolate_(t,e,n,s){let r=this.resultBuffer,a=this.sampleValues,o=this.valueSize,l=t*o,c=l-o,h=this._offsetPrev,p=this._offsetNext,d=this._weightPrev,f=this._weightNext,_=(n-e)/(s-e),b=_*_,m=b*_,u=-d*m+2*d*b-d*_,S=(1+d)*m+(-1.5-2*d)*b+(-.5+d)*_+1,R=(-1-f)*m+(1.5+f)*b+.5*_,v=f*m-f*b;for(let M=0;M!==o;++M)r[M]=u*a[h+M]+S*a[c+M]+R*a[l+M]+v*a[p+M];return r}},Ao=class extends cs{constructor(t,e,n,s){super(t,e,n,s)}interpolate_(t,e,n,s){let r=this.resultBuffer,a=this.sampleValues,o=this.valueSize,l=t*o,c=l-o,h=(n-e)/(s-e),p=1-h;for(let d=0;d!==o;++d)r[d]=a[c+d]*p+a[l+d]*h;return r}},Ro=class extends cs{constructor(t,e,n,s){super(t,e,n,s)}interpolate_(t){return this.copySampleValue_(t-1)}},Co=class extends cs{interpolate_(t,e,n,s){let r=this.resultBuffer,a=this.sampleValues,o=this.valueSize,l=t*o,c=l-o,h=this.inTangents,p=this.outTangents;if(!h||!p){let _=(n-e)/(s-e),b=1-_;for(let m=0;m!==o;++m)r[m]=a[c+m]*b+a[l+m]*_;return r}let d=o*2,f=t-1;for(let _=0;_!==o;++_){let b=a[c+_],m=a[l+_],u=f*d+_*2,S=p[u],R=p[u+1],v=t*d+_*2,M=h[v],E=h[v+1],A=ep(n,e,S,M,s);r[_]=ju(A,b,R,E,m)}return r}};function ju(i,t,e,n,s){let r=1-i;return r*r*r*t+3*r*r*i*e+3*r*i*i*n+i*i*i*s}function tp(i,t,e,n,s){let r=1-i;return 3*r*r*(e-t)+6*r*i*(n-e)+3*i*i*(s-n)}function ep(i,t,e,n,s){let r=(i-t)/(s-t);for(let a=0;a<8;a++){let o=ju(r,t,e,n,s)-i;if(Math.abs(o)<1e-10)break;let l=tp(r,t,e,n,s);if(Math.abs(l)<1e-10)break;r=Math.max(0,Math.min(1,r-o/l))}return r}var Un=class{constructor(t,e,n,s){if(t===void 0)throw new Error("THREE.KeyframeTrack: track name is undefined");if(e===void 0||e.length===0)throw new Error("THREE.KeyframeTrack: no keyframes in track named "+t);this.name=t,this.times=lr(e,this.TimeBufferType),this.values=lr(n,this.ValueBufferType),this.setInterpolation(s||this.DefaultInterpolation)}static toJSON(t){let e=t.constructor,n;if(e.toJSON!==this.toJSON)n=e.toJSON(t);else{n={name:t.name,times:lr(t.times,Array),values:lr(t.values,Array)};let s=t.getInterpolation();s!==t.DefaultInterpolation&&(n.interpolation=s),gc(t.settings)&&(n.settings={inTangents:lr(t.settings.inTangents,Array),outTangents:lr(t.settings.outTangents,Array)})}return n.type=t.ValueTypeName,n}InterpolantFactoryMethodDiscrete(t){return new Ro(this.times,this.values,this.getValueSize(),t)}InterpolantFactoryMethodLinear(t){return new Ao(this.times,this.values,this.getValueSize(),t)}InterpolantFactoryMethodSmooth(t){return new To(this.times,this.values,this.getValueSize(),t)}InterpolantFactoryMethodBezier(t){let e=new Co(this.times,this.values,this.getValueSize(),t);return this.settings&&(e.inTangents=this.settings.inTangents,e.outTangents=this.settings.outTangents),e}setInterpolation(t){let e;switch(t){case na:e=this.InterpolantFactoryMethodDiscrete;break;case xo:e=this.InterpolantFactoryMethodLinear;break;case ao:e=this.InterpolantFactoryMethodSmooth;break;case _c:e=this.InterpolantFactoryMethodBezier;break}if(e===void 0){let n="unsupported interpolation for "+this.ValueTypeName+" keyframe track named "+this.name;if(this.createInterpolant===void 0)if(t!==this.DefaultInterpolation)this.setInterpolation(this.DefaultInterpolation);else throw new Error(n);return Zt("KeyframeTrack:",n),this}return this.createInterpolant=e,this}getInterpolation(){switch(this.createInterpolant){case this.InterpolantFactoryMethodDiscrete:return na;case this.InterpolantFactoryMethodLinear:return xo;case this.InterpolantFactoryMethodSmooth:return ao;case this.InterpolantFactoryMethodBezier:return _c}}getValueSize(){return this.values.length/this.times.length}shift(t){if(t!==0){let e=this.times;for(let n=0,s=e.length;n!==s;++n)e[n]+=t}return this}scale(t){if(t!==1){let e=this.times;for(let n=0,s=e.length;n!==s;++n)e[n]*=t;gc(this.settings)&&(ru(this.settings.inTangents,t),ru(this.settings.outTangents,t))}return this}trim(t,e){let n=this.times,s=n.length,r=0,a=s-1;for(;r!==s&&n[r]<t;)++r;for(;a!==-1&&n[a]>e;)--a;if(++a,r!==0||a!==s){r>=a&&(a=Math.max(a,1),r=a-1);let o=this.getValueSize();this.times=n.slice(r,a),this.values=this.values.slice(r*o,a*o)}return this}validate(){let t=!0,e=this.getValueSize();e-Math.floor(e)!==0&&($t("KeyframeTrack: Invalid value size in track.",this),t=!1);let n=this.times,s=this.values,r=n.length;r===0&&($t("KeyframeTrack: Track is empty.",this),t=!1);let a=null;for(let o=0;o!==r;o++){let l=n[o];if(typeof l=="number"&&isNaN(l)){$t("KeyframeTrack: Time is not a valid number.",this,o,l),t=!1;break}if(a!==null&&a>l){$t("KeyframeTrack: Out of order keys.",this,o,l,a),t=!1;break}a=l}if(s!==void 0&&mf(s))for(let o=0,l=s.length;o!==l;++o){let c=s[o];if(isNaN(c)){$t("KeyframeTrack: Value is not a valid number.",this,o,c),t=!1;break}}return t}optimize(){let t=this.times.slice(),e=this.values.slice(),n=this.getValueSize(),s=this.getInterpolation()===ao,r=t.length-1,a=1;for(let o=1;o<r;++o){let l=!1,c=t[o],h=t[o+1];if(c!==h&&(o!==1||c!==t[0]))if(s)l=!0;else{let p=o*n,d=p-n,f=p+n;for(let _=0;_!==n;++_){let b=e[p+_];if(b!==e[d+_]||b!==e[f+_]){l=!0;break}}}if(l){if(o!==a){t[a]=t[o];let p=o*n,d=a*n;for(let f=0;f!==n;++f)e[d+f]=e[p+f]}++a}}if(r>0){t[a]=t[r];for(let o=r*n,l=a*n,c=0;c!==n;++c)e[l+c]=e[o+c];++a}return a!==t.length?(this.times=t.slice(0,a),this.values=e.slice(0,a*n)):(this.times=t,this.values=e),this}clone(){let t=this.times.slice(),e=this.values.slice(),n=this.constructor,s=new n(this.name,t,e);return s.createInterpolant=this.createInterpolant,gc(this.settings)&&(s.settings={inTangents:this.settings.inTangents.slice(),outTangents:this.settings.outTangents.slice()}),s}};function ru(i,t){for(let e=0,n=i.length;e!==n;e+=2)i[e]*=t}Un.prototype.ValueTypeName="";Un.prototype.TimeBufferType=Float32Array;Un.prototype.ValueBufferType=Float32Array;Un.prototype.DefaultInterpolation=xo;var hs=class extends Un{constructor(t,e,n){super(t,e,n)}};hs.prototype.ValueTypeName="bool";hs.prototype.ValueBufferType=Array;hs.prototype.DefaultInterpolation=na;hs.prototype.InterpolantFactoryMethodLinear=void 0;hs.prototype.InterpolantFactoryMethodSmooth=void 0;var Po=class extends Un{constructor(t,e,n,s){super(t,e,n,s)}};Po.prototype.ValueTypeName="color";var Io=class extends Un{constructor(t,e,n,s){super(t,e,n,s)}};Io.prototype.ValueTypeName="number";var Lo=class extends cs{constructor(t,e,n,s){super(t,e,n,s)}interpolate_(t,e,n,s){let r=this.resultBuffer,a=this.sampleValues,o=this.valueSize,l=(n-e)/(s-e),c=t*o;for(let h=c+o;c!==h;c+=4)Xe.slerpFlat(r,0,a,c-o,a,c,l);return r}},ga=class extends Un{constructor(t,e,n,s){super(t,e,n,s)}InterpolantFactoryMethodLinear(t){return new Lo(this.times,this.values,this.getValueSize(),t)}};ga.prototype.ValueTypeName="quaternion";ga.prototype.InterpolantFactoryMethodSmooth=void 0;var us=class extends Un{constructor(t,e,n){super(t,e,n)}};us.prototype.ValueTypeName="string";us.prototype.ValueBufferType=Array;us.prototype.DefaultInterpolation=na;us.prototype.InterpolantFactoryMethodLinear=void 0;us.prototype.InterpolantFactoryMethodSmooth=void 0;var Do=class extends Un{constructor(t,e,n,s){super(t,e,n,s)}};Do.prototype.ValueTypeName="vector";var zo=class{constructor(t,e,n){let s=this,r=!1,a=0,o=0,l,c=[];this.onStart=void 0,this.onLoad=t,this.onProgress=e,this.onError=n,this._abortController=null,this.itemStart=function(h){o++,r===!1&&s.onStart!==void 0&&s.onStart(h,a,o),r=!0},this.itemEnd=function(h){a++,s.onProgress!==void 0&&s.onProgress(h,a,o),a===o&&(r=!1,s.onLoad!==void 0&&s.onLoad())},this.itemError=function(h){s.onError!==void 0&&s.onError(h)},this.resolveURL=function(h){return h=h.normalize("NFC"),l?l(h):h},this.setURLModifier=function(h){return l=h,this},this.addHandler=function(h,p){return c.push(h,p),this},this.removeHandler=function(h){let p=c.indexOf(h);return p!==-1&&c.splice(p,2),this},this.getHandler=function(h){for(let p=0,d=c.length;p<d;p+=2){let f=c[p],_=c[p+1];if(f.global&&(f.lastIndex=0),f.test(h))return _}return null},this.abort=function(){return this.abortController.abort(),this._abortController=null,this}}get abortController(){return this._abortController||(this._abortController=new AbortController),this._abortController}},Qu=new zo,No=class{constructor(t){this.manager=t!==void 0?t:Qu,this.crossOrigin="anonymous",this.withCredentials=!1,this.path="",this.resourcePath="",this.requestHeader={},typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}load(){}loadAsync(t,e){let n=this;return new Promise(function(s,r){n.load(t,s,e,r)})}parse(){}setCrossOrigin(t){return this.crossOrigin=t,this}setWithCredentials(t){return this.withCredentials=t,this}setPath(t){return this.path=t,this}setResourcePath(t){return this.resourcePath=t,this}setRequestHeader(t){return this.requestHeader=t,this}abort(){return this}};No.DEFAULT_MATERIAL_NAME="__DEFAULT";var Sr=class extends dn{constructor(t,e=1){super(),this.isLight=!0,this.type="Light",this.color=new jt(t),this.intensity=e}copy(t,e){return super.copy(t,e),this.color.copy(t.color),this.intensity=t.intensity,this}toJSON(t){let e=super.toJSON(t);return e.object.color=this.color.getHex(),e.object.intensity=this.intensity,e}},Us=class extends Sr{constructor(t,e,n){super(t,n),this.isHemisphereLight=!0,this.type="HemisphereLight",this.position.copy(dn.DEFAULT_UP),this.updateMatrix(),this.groundColor=new jt(e)}copy(t,e){return super.copy(t,e),this.groundColor.copy(t.groundColor),this}toJSON(t){let e=super.toJSON(t);return e.object.groundColor=this.groundColor.getHex(),e}},xc=new be,au=new O,ou=new O,xa=class{constructor(t){this.camera=t,this.intensity=1,this.bias=0,this.biasNode=null,this.normalBias=0,this.radius=1,this.blurSamples=8,this.mapSize=new qt(512,512),this.mapType=An,this.map=null,this.mapPass=null,this.matrix=new be,this.autoUpdate=!0,this.needsUpdate=!1,this._frustum=new br,this._frameExtents=new qt(1,1),this._viewportCount=1,this._viewports=[new Oe(0,0,1,1)]}getViewportCount(){return this._viewportCount}getCamera(){return this.camera}getFrustum(){return this._frustum}updateMatrices(t){let e=this.camera;au.setFromMatrixPosition(t.matrixWorld),e.position.copy(au),ou.setFromMatrixPosition(t.target.matrixWorld),e.lookAt(ou),e.updateMatrixWorld(),this._updateMatrix(e,this.matrix,this._frustum)}_updateMatrix(t,e,n,s){xc.multiplyMatrices(t.projectionMatrix,t.matrixWorldInverse),n.setFromProjectionMatrix(xc,t.coordinateSystem,t.reversedDepth);let r=this._frameExtents,a=s?s.z/r.x:1,o=s?s.w/r.y:1,l=s?s.x/r.x:0,c=s?s.y/r.y:0;t.coordinateSystem===pr||t.reversedDepth?e.set(.5*a,0,0,.5*a+l,0,.5*o,0,.5*o+c,0,0,1,0,0,0,0,1):e.set(.5*a,0,0,.5*a+l,0,.5*o,0,.5*o+c,0,0,.5,.5,0,0,0,1),e.multiply(xc)}getViewport(t){return this._viewports[t]}getFrameExtents(){return this._frameExtents}dispose(){this.map&&this.map.dispose(),this.mapPass&&this.mapPass.dispose()}copy(t){return this.camera=t.camera.clone(),this.intensity=t.intensity,this.bias=t.bias,this.radius=t.radius,this.autoUpdate=t.autoUpdate,this.needsUpdate=t.needsUpdate,this.normalBias=t.normalBias,this.blurSamples=t.blurSamples,this.mapSize.copy(t.mapSize),this.biasNode=t.biasNode,this}clone(){return new this.constructor().copy(this)}toJSON(){let t={};return t.intensity=this.intensity,t.bias=this.bias,t.normalBias=this.normalBias,t.radius=this.radius,t.blurSamples=this.blurSamples,t.mapSize=this.mapSize.toArray(),t.camera=this.camera.toJSON(!1).object,delete t.camera.matrix,t}},so=new O,ro=new Xe,pi=new O,_a=class extends dn{constructor(){super(),this.isCamera=!0,this.type="Camera",this.matrixWorldInverse=new be,this.projectionMatrix=new be,this.projectionMatrixInverse=new be,this.coordinateSystem=ni,this._reversedDepth=!1}get reversedDepth(){return this._reversedDepth}copy(t,e){return super.copy(t,e),this.matrixWorldInverse.copy(t.matrixWorldInverse),this.projectionMatrix.copy(t.projectionMatrix),this.projectionMatrixInverse.copy(t.projectionMatrixInverse),this.coordinateSystem=t.coordinateSystem,this}getWorldDirection(t){return super.getWorldDirection(t).negate()}updateMatrixWorld(t){super.updateMatrixWorld(t),this.matrixWorld.decompose(so,ro,pi),pi.x===1&&pi.y===1&&pi.z===1?this.matrixWorldInverse.copy(this.matrixWorld).invert():this.matrixWorldInverse.compose(so,ro,pi.set(1,1,1)).invert()}updateWorldMatrix(t,e,n=!1){super.updateWorldMatrix(t,e,n),this.matrixWorld.decompose(so,ro,pi),pi.x===1&&pi.y===1&&pi.z===1?this.matrixWorldInverse.copy(this.matrixWorld).invert():this.matrixWorldInverse.compose(so,ro,pi.set(1,1,1)).invert()}clone(){return new this.constructor().copy(this)}},ss=new O,lu=new qt,cu=new qt,Ye=class extends _a{constructor(t=50,e=1,n=.1,s=2e3){super(),this.isPerspectiveCamera=!0,this.type="PerspectiveCamera",this.fov=t,this.zoom=1,this.near=n,this.far=s,this.focus=10,this.aspect=e,this.view=null,this.filmGauge=35,this.filmOffset=0,this.updateProjectionMatrix()}copy(t,e){return super.copy(t,e),this.fov=t.fov,this.zoom=t.zoom,this.near=t.near,this.far=t.far,this.focus=t.focus,this.aspect=t.aspect,this.view=t.view===null?null:Object.assign({},t.view),this.filmGauge=t.filmGauge,this.filmOffset=t.filmOffset,this}setFocalLength(t){let e=.5*this.getFilmHeight()/t;this.fov=gr*2*Math.atan(e),this.updateProjectionMatrix()}getFocalLength(){let t=Math.tan(ta*.5*this.fov);return .5*this.getFilmHeight()/t}getEffectiveFOV(){return gr*2*Math.atan(Math.tan(ta*.5*this.fov)/this.zoom)}getFilmWidth(){return this.filmGauge*Math.min(this.aspect,1)}getFilmHeight(){return this.filmGauge/Math.max(this.aspect,1)}getViewBounds(t,e,n){ss.set(-1,-1,.5).applyMatrix4(this.projectionMatrixInverse),e.set(ss.x,ss.y).multiplyScalar(-t/ss.z),ss.set(1,1,.5).applyMatrix4(this.projectionMatrixInverse),n.set(ss.x,ss.y).multiplyScalar(-t/ss.z)}getViewSize(t,e){return this.getViewBounds(t,lu,cu),e.subVectors(cu,lu)}setViewOffset(t,e,n,s,r,a){this.aspect=t/e,this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=t,this.view.fullHeight=e,this.view.offsetX=n,this.view.offsetY=s,this.view.width=r,this.view.height=a,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){let t=this.near,e=t*Math.tan(ta*.5*this.fov)/this.zoom,n=2*e,s=this.aspect*n,r=-.5*s,a=this.view;if(this.view!==null&&this.view.enabled){let l=a.fullWidth,c=a.fullHeight;r+=a.offsetX*s/l,e-=a.offsetY*n/c,s*=a.width/l,n*=a.height/c}let o=this.filmOffset;o!==0&&(r+=t*o/this.getFilmWidth()),this.projectionMatrix.makePerspective(r,r+s,e,e-n,t,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(t){let e=super.toJSON(t);return e.object.fov=this.fov,e.object.zoom=this.zoom,e.object.near=this.near,e.object.far=this.far,e.object.focus=this.focus,e.object.aspect=this.aspect,this.view!==null&&(e.object.view=Object.assign({},this.view)),e.object.filmGauge=this.filmGauge,e.object.filmOffset=this.filmOffset,e}};var Mc=class extends xa{constructor(){super(new Ye(90,1,.5,500)),this.isPointLightShadow=!0}},yi=class extends Sr{constructor(t,e,n=0,s=2){super(t,e),this.isPointLight=!0,this.type="PointLight",this.distance=n,this.decay=s,this.shadow=new Mc}get power(){return this.intensity*4*Math.PI}set power(t){this.intensity=t/(4*Math.PI)}dispose(){super.dispose(),this.shadow.dispose()}copy(t,e){return super.copy(t,e),this.distance=t.distance,this.decay=t.decay,this.shadow=t.shadow.clone(),this}toJSON(t){let e=super.toJSON(t);return e.object.distance=this.distance,e.object.decay=this.decay,e.object.shadow=this.shadow.toJSON(),e}},Er=class extends _a{constructor(t=-1,e=1,n=1,s=-1,r=.1,a=2e3){super(),this.isOrthographicCamera=!0,this.type="OrthographicCamera",this.zoom=1,this.view=null,this.left=t,this.right=e,this.top=n,this.bottom=s,this.near=r,this.far=a,this.updateProjectionMatrix()}copy(t,e){return super.copy(t,e),this.left=t.left,this.right=t.right,this.top=t.top,this.bottom=t.bottom,this.near=t.near,this.far=t.far,this.zoom=t.zoom,this.view=t.view===null?null:Object.assign({},t.view),this}setViewOffset(t,e,n,s,r,a){this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=t,this.view.fullHeight=e,this.view.offsetX=n,this.view.offsetY=s,this.view.width=r,this.view.height=a,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){let t=(this.right-this.left)/(2*this.zoom),e=(this.top-this.bottom)/(2*this.zoom),n=(this.right+this.left)/2,s=(this.top+this.bottom)/2,r=n-t,a=n+t,o=s+e,l=s-e;if(this.view!==null&&this.view.enabled){let c=(this.right-this.left)/this.view.fullWidth/this.zoom,h=(this.top-this.bottom)/this.view.fullHeight/this.zoom;r+=c*this.view.offsetX,a=r+c*this.view.width,o-=h*this.view.offsetY,l=o-h*this.view.height}this.projectionMatrix.makeOrthographic(r,a,o,l,this.near,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(t){let e=super.toJSON(t);return e.object.zoom=this.zoom,e.object.left=this.left,e.object.right=this.right,e.object.top=this.top,e.object.bottom=this.bottom,e.object.near=this.near,e.object.far=this.far,this.view!==null&&(e.object.view=Object.assign({},this.view)),e}},Sc=class extends xa{constructor(){super(new Er(-5,5,5,-5,.5,500)),this.isDirectionalLightShadow=!0}},Vi=class extends Sr{constructor(t,e){super(t,e),this.isDirectionalLight=!0,this.type="DirectionalLight",this.position.copy(dn.DEFAULT_UP),this.updateMatrix(),this.target=new dn,this.shadow=new Sc}dispose(){super.dispose(),this.shadow.dispose()}copy(t){return super.copy(t),this.target=t.target.clone(),this.shadow=t.shadow.clone(),this}toJSON(t){let e=super.toJSON(t);return e.object.shadow=this.shadow.toJSON(),e.object.target=this.target.uuid,e}};var cr=-90,hr=1,Uo=class extends dn{constructor(t,e,n){super(),this.type="CubeCamera",this.renderTarget=n,this.coordinateSystem=null,this.activeMipmapLevel=0;let s=new Ye(cr,hr,t,e);s.layers=this.layers,this.add(s);let r=new Ye(cr,hr,t,e);r.layers=this.layers,this.add(r);let a=new Ye(cr,hr,t,e);a.layers=this.layers,this.add(a);let o=new Ye(cr,hr,t,e);o.layers=this.layers,this.add(o);let l=new Ye(cr,hr,t,e);l.layers=this.layers,this.add(l);let c=new Ye(cr,hr,t,e);c.layers=this.layers,this.add(c)}updateCoordinateSystem(){let t=this.coordinateSystem,e=this.children.concat(),[n,s,r,a,o,l]=e;for(let c of e)this.remove(c);if(t===ni)n.up.set(0,1,0),n.lookAt(1,0,0),s.up.set(0,1,0),s.lookAt(-1,0,0),r.up.set(0,0,-1),r.lookAt(0,1,0),a.up.set(0,0,1),a.lookAt(0,-1,0),o.up.set(0,1,0),o.lookAt(0,0,1),l.up.set(0,1,0),l.lookAt(0,0,-1);else if(t===pr)n.up.set(0,-1,0),n.lookAt(-1,0,0),s.up.set(0,-1,0),s.lookAt(1,0,0),r.up.set(0,0,1),r.lookAt(0,1,0),a.up.set(0,0,-1),a.lookAt(0,-1,0),o.up.set(0,-1,0),o.lookAt(0,0,1),l.up.set(0,-1,0),l.lookAt(0,0,-1);else throw new Error("THREE.CubeCamera.updateCoordinateSystem(): Invalid coordinate system: "+t);for(let c of e)this.add(c),c.updateMatrixWorld()}update(t,e){this.parent===null&&this.updateMatrixWorld();let{renderTarget:n,activeMipmapLevel:s}=this;this.coordinateSystem!==t.coordinateSystem&&(this.coordinateSystem=t.coordinateSystem,this.updateCoordinateSystem());let[r,a,o,l,c,h]=this.children,p=t.getRenderTarget(),d=t.getActiveCubeFace(),f=t.getActiveMipmapLevel(),_=t.xr.enabled;t.xr.enabled=!1;let b=n.texture.generateMipmaps;n.texture.generateMipmaps=!1;let m=!1;t.isWebGLRenderer===!0?m=t.state.buffers.depth.getReversed():m=t.reversedDepthBuffer,t.setRenderTarget(n,0,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,r),t.setRenderTarget(n,1,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,a),t.setRenderTarget(n,2,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,o),t.setRenderTarget(n,3,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,l),t.setRenderTarget(n,4,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,c),n.texture.generateMipmaps=b,t.setRenderTarget(n,5,s),m&&t.autoClear===!1&&t.clearDepth(),t.render(e,h),t.setRenderTarget(p,d,f),t.xr.enabled=_,n.texture.needsPMREMUpdate=!0}},Fo=class extends Ye{constructor(t=[]){super(),this.isArrayCamera=!0,this.isMultiViewCamera=!1,this.cameras=t}};var Jc="\\[\\]\\.:\\/",np=new RegExp("["+Jc+"]","g"),jc="[^"+Jc+"]",ip="[^"+Jc.replace("\\.","")+"]",sp=/((?:WC+[\/:])*)/.source.replace("WC",jc),rp=/(WCOD+)?/.source.replace("WCOD",ip),ap=/(?:\.(WC+)(?:\[(.+)\])?)?/.source.replace("WC",jc),op=/\.(WC+)(?:\[(.+)\])?/.source.replace("WC",jc),lp=new RegExp("^"+sp+rp+ap+op+"$"),cp=["material","materials","bones","map"],Ec=class{constructor(t,e,n){let s=n||Ue.parseTrackName(e);this._targetGroup=t,this._bindings=t.subscribe_(e,s)}getValue(t,e){this.bind();let n=this._targetGroup.nCachedObjects_,s=this._bindings[n];s!==void 0&&s.getValue(t,e)}setValue(t,e){let n=this._bindings;for(let s=this._targetGroup.nCachedObjects_,r=n.length;s!==r;++s)n[s].setValue(t,e)}bind(){let t=this._bindings;for(let e=this._targetGroup.nCachedObjects_,n=t.length;e!==n;++e)t[e].bind()}unbind(){let t=this._bindings;for(let e=this._targetGroup.nCachedObjects_,n=t.length;e!==n;++e)t[e].unbind()}},Ue=class i{constructor(t,e,n){this.path=e,this.parsedPath=n||i.parseTrackName(e),this.node=i.findNode(t,this.parsedPath.nodeName),this.rootNode=t,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}static create(t,e,n){return t&&t.isAnimationObjectGroup?new i.Composite(t,e,n):new i(t,e,n)}static sanitizeNodeName(t){return t.replace(/\s/g,"_").replace(np,"")}static parseTrackName(t){let e=lp.exec(t);if(e===null)throw new Error("THREE.PropertyBinding: Cannot parse trackName: "+t);let n={nodeName:e[2],objectName:e[3],objectIndex:e[4],propertyName:e[5],propertyIndex:e[6]},s=n.nodeName&&n.nodeName.lastIndexOf(".");if(s!==void 0&&s!==-1){let r=n.nodeName.substring(s+1);cp.indexOf(r)!==-1&&(n.nodeName=n.nodeName.substring(0,s),n.objectName=r)}if(n.propertyName===null||n.propertyName.length===0)throw new Error("THREE.PropertyBinding: can not parse propertyName from trackName: "+t);return n}static findNode(t,e){if(e===void 0||e===""||e==="."||e===-1||e===t.name||e===t.uuid)return t;if(t.skeleton){let n=t.skeleton.getBoneByName(e);if(n!==void 0)return n}if(t.children){let n=function(r){for(let a=0;a<r.length;a++){let o=r[a];if(o.name===e||o.uuid===e)return o;let l=n(o.children);if(l)return l}return null},s=n(t.children);if(s)return s}return null}_getValue_unavailable(){}_setValue_unavailable(){}_getValue_direct(t,e){t[e]=this.targetObject[this.propertyName]}_getValue_array(t,e){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)t[e++]=n[s]}_getValue_arrayElement(t,e){t[e]=this.resolvedProperty[this.propertyIndex]}_getValue_toArray(t,e){this.resolvedProperty.toArray(t,e)}_setValue_direct(t,e){this.targetObject[this.propertyName]=t[e]}_setValue_direct_setNeedsUpdate(t,e){this.targetObject[this.propertyName]=t[e],this.targetObject.needsUpdate=!0}_setValue_direct_setMatrixWorldNeedsUpdate(t,e){this.targetObject[this.propertyName]=t[e],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_array(t,e){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)n[s]=t[e++]}_setValue_array_setNeedsUpdate(t,e){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)n[s]=t[e++];this.targetObject.needsUpdate=!0}_setValue_array_setMatrixWorldNeedsUpdate(t,e){let n=this.resolvedProperty;for(let s=0,r=n.length;s!==r;++s)n[s]=t[e++];this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_arrayElement(t,e){this.resolvedProperty[this.propertyIndex]=t[e]}_setValue_arrayElement_setNeedsUpdate(t,e){this.resolvedProperty[this.propertyIndex]=t[e],this.targetObject.needsUpdate=!0}_setValue_arrayElement_setMatrixWorldNeedsUpdate(t,e){this.resolvedProperty[this.propertyIndex]=t[e],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_fromArray(t,e){this.resolvedProperty.fromArray(t,e)}_setValue_fromArray_setNeedsUpdate(t,e){this.resolvedProperty.fromArray(t,e),this.targetObject.needsUpdate=!0}_setValue_fromArray_setMatrixWorldNeedsUpdate(t,e){this.resolvedProperty.fromArray(t,e),this.targetObject.matrixWorldNeedsUpdate=!0}_getValue_unbound(t,e){this.bind(),this.getValue(t,e)}_setValue_unbound(t,e){this.bind(),this.setValue(t,e)}bind(){let t=this.node,e=this.parsedPath,n=e.objectName,s=e.propertyName,r=e.propertyIndex;if(t||(t=i.findNode(this.rootNode,e.nodeName),this.node=t),this.getValue=this._getValue_unavailable,this.setValue=this._setValue_unavailable,!t){Zt("PropertyBinding: No target node found for track: "+this.path+".");return}if(n){let c=e.objectIndex;switch(n){case"materials":if(!t.material){$t("PropertyBinding: Can not bind to material as node does not have a material.",this);return}if(!t.material.materials){$t("PropertyBinding: Can not bind to material.materials as node.material does not have a materials array.",this);return}t=t.material.materials;break;case"bones":if(!t.skeleton){$t("PropertyBinding: Can not bind to bones as node does not have a skeleton.",this);return}t=t.skeleton.bones;for(let h=0;h<t.length;h++)if(t[h].name===c){c=h;break}break;case"map":if("map"in t){t=t.map;break}if(!t.material){$t("PropertyBinding: Can not bind to material as node does not have a material.",this);return}if(!t.material.map){$t("PropertyBinding: Can not bind to material.map as node.material does not have a map.",this);return}t=t.material.map;break;default:if(t[n]===void 0){$t("PropertyBinding: Can not bind to objectName of node undefined.",this);return}t=t[n]}if(c!==void 0){if(t[c]===void 0){$t("PropertyBinding: Trying to bind to objectIndex of objectName, but is undefined.",this,t);return}t=t[c]}}let a=t[s];if(a===void 0){let c=e.nodeName;$t("PropertyBinding: Trying to update property for track: "+c+"."+s+" but it wasn't found.",t);return}let o=this.Versioning.None;this.targetObject=t,t.isMaterial===!0?o=this.Versioning.NeedsUpdate:t.isObject3D===!0&&(o=this.Versioning.MatrixWorldNeedsUpdate);let l=this.BindingType.Direct;if(r!==void 0){if(s==="morphTargetInfluences"){if(!t.geometry){$t("PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.",this);return}if(!t.geometry.morphAttributes){$t("PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.morphAttributes.",this);return}t.morphTargetDictionary[r]!==void 0&&(r=t.morphTargetDictionary[r])}l=this.BindingType.ArrayElement,this.resolvedProperty=a,this.propertyIndex=r}else a.fromArray!==void 0&&a.toArray!==void 0?(l=this.BindingType.HasFromToArray,this.resolvedProperty=a):Array.isArray(a)?(l=this.BindingType.EntireArray,this.resolvedProperty=a):this.propertyName=s;this.getValue=this.GetterByBindingType[l],this.setValue=this.SetterByBindingTypeAndVersioning[l][o]}unbind(){this.node=null,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}};Ue.Composite=Ec;Ue.prototype.BindingType={Direct:0,EntireArray:1,ArrayElement:2,HasFromToArray:3};Ue.prototype.Versioning={None:0,NeedsUpdate:1,MatrixWorldNeedsUpdate:2};Ue.prototype.GetterByBindingType=[Ue.prototype._getValue_direct,Ue.prototype._getValue_array,Ue.prototype._getValue_arrayElement,Ue.prototype._getValue_toArray];Ue.prototype.SetterByBindingTypeAndVersioning=[[Ue.prototype._setValue_direct,Ue.prototype._setValue_direct_setNeedsUpdate,Ue.prototype._setValue_direct_setMatrixWorldNeedsUpdate],[Ue.prototype._setValue_array,Ue.prototype._setValue_array_setNeedsUpdate,Ue.prototype._setValue_array_setMatrixWorldNeedsUpdate],[Ue.prototype._setValue_arrayElement,Ue.prototype._setValue_arrayElement_setNeedsUpdate,Ue.prototype._setValue_arrayElement_setMatrixWorldNeedsUpdate],[Ue.prototype._setValue_fromArray,Ue.prototype._setValue_fromArray_setNeedsUpdate,Ue.prototype._setValue_fromArray_setMatrixWorldNeedsUpdate]];var gy=new Float32Array(1);var hu=new be,Fs=class{constructor(t,e,n=0,s=1/0){this.ray=new zs(t,e),this.near=n,this.far=s,this.camera=null,this.layers=new _r,this.params={Mesh:{},Line:{threshold:1},LOD:{},Points:{threshold:1},Sprite:{}}}set(t,e){this.ray.set(t,e)}setFromCamera(t,e){e.isPerspectiveCamera?(this.ray.origin.setFromMatrixPosition(e.matrixWorld),this.ray.direction.set(t.x,t.y,.5).unproject(e).sub(this.ray.origin).normalize(),this.camera=e):e.isOrthographicCamera?(this.ray.origin.set(t.x,t.y,e.projectionMatrix.elements[14]).unproject(e),this.ray.direction.set(0,0,-1).transformDirection(e.matrixWorld),this.camera=e):$t("Raycaster: Unsupported camera type: "+e.type)}setFromXRController(t){return hu.identity().extractRotation(t.matrixWorld),this.ray.origin.setFromMatrixPosition(t.matrixWorld),this.ray.direction.set(0,0,-1).applyMatrix4(hu),this}intersectObject(t,e=!0,n=[]){return wc(t,this,n,e),n.sort(uu),n}intersectObjects(t,e=!0,n=[]){for(let s=0,r=t.length;s<r;s++)wc(t[s],this,n,e);return n.sort(uu),n}};function uu(i,t){return i.distance-t.distance}function wc(i,t,e,n){let s=!0;if(i.layers.test(t.layers)&&i.raycast(t,e)===!1&&(s=!1),s===!0&&n===!0){let r=i.children;for(let a=0,o=r.length;a<o;a++)wc(r[a],t,e,!0)}}var Tn=class{constructor(t=1,e=0,n=0){this.radius=t,this.phi=e,this.theta=n}set(t,e,n){return this.radius=t,this.phi=e,this.theta=n,this}copy(t){return this.radius=t.radius,this.phi=t.phi,this.theta=t.theta,this}makeSafe(){return this.phi=he(this.phi,1e-6,Math.PI-1e-6),this}setFromVector3(t){return this.setFromCartesianCoords(t.x,t.y,t.z)}setFromCartesianCoords(t,e,n){return this.radius=Math.sqrt(t*t+e*e+n*n),this.radius===0?(this.theta=0,this.phi=0):(this.theta=Math.atan2(t,n),this.phi=Math.acos(he(e/this.radius,-1,1))),this}clone(){return new this.constructor().copy(this)}};var sh=class sh{constructor(t,e,n,s){this.elements=[1,0,0,1],t!==void 0&&this.set(t,e,n,s)}identity(){return this.set(1,0,0,1),this}fromArray(t,e=0){for(let n=0;n<4;n++)this.elements[n]=t[n+e];return this}set(t,e,n,s){let r=this.elements;return r[0]=t,r[2]=e,r[1]=n,r[3]=s,this}};sh.prototype.isMatrix2=!0;var Tc=sh;var ya=class extends ii{constructor(t,e=null){super(),this.object=t,this.domElement=e,this.enabled=!0,this.state=-1,this.keys={},this.mouseButtons={LEFT:null,MIDDLE:null,RIGHT:null},this.touches={ONE:null,TWO:null}}connect(t){this.domElement!==null&&this.disconnect(),this.domElement=t}disconnect(){}dispose(){}update(){}};function Qc(i,t,e,n){let s=hp(n);switch(e){case Xc:return i*t;case Xo:return i*t/s.components*s.byteLength;case qo:return i*t/s.components*s.byteLength;case _s:return i*t*2/s.components*s.byteLength;case Yo:return i*t*2/s.components*s.byteLength;case qc:return i*t*3/s.components*s.byteLength;case Gn:return i*t*4/s.components*s.byteLength;case Zo:return i*t*4/s.components*s.byteLength;case Ma:case Sa:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*8;case Ea:case wa:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*16;case Ko:case jo:return Math.max(i,16)*Math.max(t,8)/4;case $o:case Jo:return Math.max(i,8)*Math.max(t,8)/2;case Qo:case tl:case nl:case il:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*8;case el:case Ta:case sl:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*16;case rl:return Math.floor((i+3)/4)*Math.floor((t+3)/4)*16;case al:return Math.floor((i+4)/5)*Math.floor((t+3)/4)*16;case ol:return Math.floor((i+4)/5)*Math.floor((t+4)/5)*16;case ll:return Math.floor((i+5)/6)*Math.floor((t+4)/5)*16;case cl:return Math.floor((i+5)/6)*Math.floor((t+5)/6)*16;case hl:return Math.floor((i+7)/8)*Math.floor((t+4)/5)*16;case ul:return Math.floor((i+7)/8)*Math.floor((t+5)/6)*16;case dl:return Math.floor((i+7)/8)*Math.floor((t+7)/8)*16;case fl:return Math.floor((i+9)/10)*Math.floor((t+4)/5)*16;case pl:return Math.floor((i+9)/10)*Math.floor((t+5)/6)*16;case ml:return Math.floor((i+9)/10)*Math.floor((t+7)/8)*16;case gl:return Math.floor((i+9)/10)*Math.floor((t+9)/10)*16;case xl:return Math.floor((i+11)/12)*Math.floor((t+9)/10)*16;case _l:return Math.floor((i+11)/12)*Math.floor((t+11)/12)*16;case yl:case vl:case bl:return Math.ceil(i/4)*Math.ceil(t/4)*16;case Ml:case Sl:return Math.ceil(i/4)*Math.ceil(t/4)*8;case Aa:case El:return Math.ceil(i/4)*Math.ceil(t/4)*16}throw new Error(`Unable to determine texture byte length for ${e} format.`)}function hp(i){switch(i){case An:case Hc:return{byteLength:1,components:1};case Ar:case Vc:case ai:return{byteLength:2,components:1};case Go:case Wo:return{byteLength:2,components:4};case ri:case Vo:case Vn:return{byteLength:4,components:1};case Gc:case Wc:return{byteLength:4,components:3}}throw new Error(`THREE.TextureUtils: Unknown texture type ${i}.`)}typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("register",{detail:{revision:"186"}}));typeof window<"u"&&(window.__THREE__?Zt("WARNING: Multiple instances of Three.js being imported."):window.__THREE__="186");/**
 * @license
 * Copyright 2010-2026 Three.js Authors
 * SPDX-License-Identifier: MIT
 */function bd(){let i=null,t=!1,e=null,n=null;function s(r,a){n=i.requestAnimationFrame(s),e(r,a)}return{start:function(){t!==!0&&e!==null&&i!==null&&(n=i.requestAnimationFrame(s),t=!0)},stop:function(){i!==null&&i.cancelAnimationFrame(n),t=!1},setAnimationLoop:function(r){e=r},setContext:function(r){i=r}}}function xp(i){let t=new WeakMap;function e(o,l){let c=o.array,h=o.usage,p=c.byteLength,d=i.createBuffer();i.bindBuffer(l,d),i.bufferData(l,c,h),o.onUploadCallback();let f;if(c instanceof Float32Array)f=i.FLOAT;else if(typeof Float16Array<"u"&&c instanceof Float16Array)f=i.HALF_FLOAT;else if(c instanceof Uint16Array)o.isFloat16BufferAttribute?f=i.HALF_FLOAT:f=i.UNSIGNED_SHORT;else if(c instanceof Int16Array)f=i.SHORT;else if(c instanceof Uint32Array)f=i.UNSIGNED_INT;else if(c instanceof Int32Array)f=i.INT;else if(c instanceof Int8Array)f=i.BYTE;else if(c instanceof Uint8Array)f=i.UNSIGNED_BYTE;else if(c instanceof Uint8ClampedArray)f=i.UNSIGNED_BYTE;else throw new Error("THREE.WebGLAttributes: Unsupported buffer data format: "+c);return{buffer:d,type:f,bytesPerElement:c.BYTES_PER_ELEMENT,version:o.version,size:p}}function n(o,l,c){let h=l.array,p=l.updateRanges;if(i.bindBuffer(c,o),p.length===0)i.bufferSubData(c,0,h);else{p.sort((f,_)=>f.start-_.start);let d=0;for(let f=1;f<p.length;f++){let _=p[d],b=p[f];b.start<=_.start+_.count+1?_.count=Math.max(_.count,b.start+b.count-_.start):(++d,p[d]=b)}p.length=d+1;for(let f=0,_=p.length;f<_;f++){let b=p[f];i.bufferSubData(c,b.start*h.BYTES_PER_ELEMENT,h,b.start,b.count)}l.clearUpdateRanges()}l.onUploadCallback()}function s(o){return o.isInterleavedBufferAttribute&&(o=o.data),t.get(o)}function r(o){o.isInterleavedBufferAttribute&&(o=o.data);let l=t.get(o);l&&(i.deleteBuffer(l.buffer),t.delete(o))}function a(o,l){if(o.isInterleavedBufferAttribute&&(o=o.data),o.isGLBufferAttribute){let h=t.get(o);(!h||h.version<o.version)&&t.set(o,{buffer:o.buffer,type:o.type,bytesPerElement:o.elementSize,version:o.version});return}let c=t.get(o);if(c===void 0)t.set(o,e(o,l));else if(c.version<o.version){if(c.size!==o.array.byteLength)throw new Error("THREE.WebGLAttributes: The size of the buffer attribute's array buffer does not match the original size. Resizing buffer attributes is not supported.");n(c.buffer,o,l),c.version=o.version}}return{get:s,remove:r,update:a}}var _p=`#ifdef USE_ALPHAHASH
	if ( diffuseColor.a < getAlphaHashThreshold( vPosition ) ) discard;
#endif`,yp=`#ifdef USE_ALPHAHASH
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
#endif`,vp=`#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, vAlphaMapUv ).g;
#endif`,bp=`#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,Mp=`#ifdef USE_ALPHATEST
	#ifdef ALPHA_TO_COVERAGE
	diffuseColor.a = smoothstep( alphaTest, alphaTest + fwidth( diffuseColor.a ), diffuseColor.a );
	if ( diffuseColor.a == 0.0 ) discard;
	#else
	if ( diffuseColor.a < alphaTest ) discard;
	#endif
#endif`,Sp=`#ifdef USE_ALPHATEST
	uniform float alphaTest;
#endif`,Ep=`#ifdef USE_AOMAP
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
#endif`,wp=`#ifdef USE_AOMAP
	uniform sampler2D aoMap;
	uniform float aoMapIntensity;
#endif`,Tp=`#ifdef USE_BATCHING
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
#endif`,Ap=`#ifdef USE_BATCHING
	mat4 batchingMatrix = getBatchingMatrix( getIndirectIndex( gl_DrawID ) );
#endif`,Rp=`vec3 transformed = vec3( position );
#ifdef USE_ALPHAHASH
	vPosition = vec3( position );
#endif`,Cp=`vec3 objectNormal = vec3( normal );
#ifdef USE_TANGENT
	vec3 objectTangent = vec3( tangent.xyz );
#endif`,Pp=`float G_BlinnPhong_Implicit( ) {
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
} // validated`,Ip=`#ifdef USE_IRIDESCENCE
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
#endif`,Lp=`#ifdef USE_BUMPMAP
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
#endif`,Dp=`#if NUM_CLIPPING_PLANES > 0
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
#endif`,zp=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
	uniform vec4 clippingPlanes[ NUM_CLIPPING_PLANES ];
#endif`,Np=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
#endif`,Up=`#if NUM_CLIPPING_PLANES > 0
	vClipPosition = - mvPosition.xyz;
#endif`,Fp=`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )
	diffuseColor *= vColor;
#endif`,Op=`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )
	varying vec4 vColor;
#endif`,Bp=`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	varying vec4 vColor;
#endif`,kp=`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
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
#endif`,Hp=`#define PI 3.141592653589793
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
} // validated`,Vp=`#ifdef ENVMAP_TYPE_CUBE_UV
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
#endif`,Gp=`vec3 transformedNormal = objectNormal;
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
#endif`,Wp=`#ifdef USE_DISPLACEMENTMAP
	uniform sampler2D displacementMap;
	uniform float displacementScale;
	uniform float displacementBias;
#endif`,Xp=`#ifdef USE_DISPLACEMENTMAP
	transformed += normalize( objectNormal ) * ( texture2D( displacementMap, vDisplacementMapUv ).x * displacementScale + displacementBias );
#endif`,qp=`#ifdef USE_EMISSIVEMAP
	vec4 emissiveColor = texture2D( emissiveMap, vEmissiveMapUv );
	#ifdef DECODE_VIDEO_TEXTURE_EMISSIVE
		emissiveColor = sRGBTransferEOTF( emissiveColor );
	#endif
	totalEmissiveRadiance *= emissiveColor.rgb;
#endif`,Yp=`#ifdef USE_EMISSIVEMAP
	uniform sampler2D emissiveMap;
#endif`,Zp="gl_FragColor = linearToOutputTexel( gl_FragColor );",$p=`vec4 LinearTransferOETF( in vec4 value ) {
	return value;
}
vec4 sRGBTransferEOTF( in vec4 value ) {
	return vec4( mix( pow( value.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), value.rgb * 0.0773993808, vec3( lessThanEqual( value.rgb, vec3( 0.04045 ) ) ) ), value.a );
}
vec4 sRGBTransferOETF( in vec4 value ) {
	return vec4( mix( pow( value.rgb, vec3( 0.41666 ) ) * 1.055 - vec3( 0.055 ), value.rgb * 12.92, vec3( lessThanEqual( value.rgb, vec3( 0.0031308 ) ) ) ), value.a );
}`,Kp=`#ifdef USE_ENVMAP
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
#endif`,Jp=`#ifdef USE_ENVMAP
	uniform float envMapIntensity;
	uniform mat3 envMapRotation;
	#ifdef ENVMAP_TYPE_CUBE
		uniform samplerCube envMap;
	#else
		uniform sampler2D envMap;
	#endif
#endif`,jp=`#ifdef USE_ENVMAP
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
#endif`,Qp=`#ifdef USE_ENVMAP
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		
		varying vec3 vWorldPosition;
	#else
		varying vec3 vReflect;
		uniform float refractionRatio;
	#endif
#endif`,tm=`#ifdef USE_ENVMAP
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
#endif`,em=`#ifdef USE_FOG
	vFogDepth = - mvPosition.z;
#endif`,nm=`#ifdef USE_FOG
	varying float vFogDepth;
#endif`,im=`#ifdef USE_FOG
	#ifdef FOG_EXP2
		float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
	#else
		float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );
	#endif
	gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );
#endif`,sm=`#ifdef USE_FOG
	uniform vec3 fogColor;
	varying float vFogDepth;
	#ifdef FOG_EXP2
		uniform float fogDensity;
	#else
		uniform float fogNear;
		uniform float fogFar;
	#endif
#endif`,rm=`#ifdef USE_GRADIENTMAP
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
}`,am=`#ifdef USE_LIGHTMAP
	uniform sampler2D lightMap;
	uniform float lightMapIntensity;
#endif`,om=`LambertMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularStrength = specularStrength;`,lm=`varying vec3 vViewPosition;
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
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Lambert`,cm=`uniform bool receiveShadow;
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
#include <lightprobes_pars_fragment>`,hm=`#ifdef USE_ENVMAP
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
#endif`,um=`ToonMaterial material;
material.diffuseColor = diffuseColor.rgb;`,dm=`varying vec3 vViewPosition;
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
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Toon`,fm=`BlinnPhongMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularColor = specular;
material.specularShininess = shininess;
material.specularStrength = specularStrength;`,pm=`varying vec3 vViewPosition;
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
#define RE_IndirectDiffuse		RE_IndirectDiffuse_BlinnPhong`,mm=`PhysicalMaterial material;
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
#endif`,gm=`uniform sampler2D dfgLUT;
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
}`,xm=`
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
#endif`,_m=`#if defined( RE_IndirectDiffuse )
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
#endif`,ym=`#if defined( RE_IndirectDiffuse )
	#if defined( LAMBERT ) || defined( PHONG )
		irradiance += iblIrradiance;
	#endif
	RE_IndirectDiffuse( irradiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif
#if defined( RE_IndirectSpecular )
	RE_IndirectSpecular( radiance, iblIrradiance, clearcoatRadiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif`,vm=`#ifdef USE_LIGHT_PROBES_GRID
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
#endif`,bm=`#if defined( USE_LOGARITHMIC_DEPTH_BUFFER )
	gl_FragDepth = vIsPerspective == 0.0 ? gl_FragCoord.z : log2( vFragDepth ) * logDepthBufFC * 0.5;
#endif`,Mm=`#if defined( USE_LOGARITHMIC_DEPTH_BUFFER )
	uniform float logDepthBufFC;
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,Sm=`#ifdef USE_LOGARITHMIC_DEPTH_BUFFER
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,Em=`#ifdef USE_LOGARITHMIC_DEPTH_BUFFER
	vFragDepth = 1.0 + gl_Position.w;
	vIsPerspective = float( isPerspectiveMatrix( projectionMatrix ) );
#endif`,wm=`#ifdef USE_MAP
	vec4 sampledDiffuseColor = texture2D( map, vMapUv );
	#ifdef DECODE_VIDEO_TEXTURE
		sampledDiffuseColor = sRGBTransferEOTF( sampledDiffuseColor );
	#endif
	diffuseColor *= sampledDiffuseColor;
#endif`,Tm=`#ifdef USE_MAP
	uniform sampler2D map;
#endif`,Am=`#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
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
#endif`,Rm=`#if defined( USE_POINTS_UV )
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
#endif`,Cm=`float metalnessFactor = metalness;
#ifdef USE_METALNESSMAP
	vec4 texelMetalness = texture2D( metalnessMap, vMetalnessMapUv );
	metalnessFactor *= texelMetalness.b;
#endif`,Pm=`#ifdef USE_METALNESSMAP
	uniform sampler2D metalnessMap;
#endif`,Im=`#ifdef USE_INSTANCING_MORPH
	float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	float morphTargetBaseInfluence = texelFetch( morphTexture, ivec2( 0, gl_InstanceID ), 0 ).r;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		morphTargetInfluences[i] =  texelFetch( morphTexture, ivec2( i + 1, gl_InstanceID ), 0 ).r;
	}
#endif`,Lm=`#if defined( USE_MORPHCOLORS )
	vColor *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		#if defined( USE_COLOR_ALPHA )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ) * morphTargetInfluences[ i ];
		#elif defined( USE_COLOR )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ).rgb * morphTargetInfluences[ i ];
		#endif
	}
#endif`,Dm=`#ifdef USE_MORPHNORMALS
	objectNormal *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) objectNormal += getMorph( gl_VertexID, i, 1 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,zm=`#ifdef USE_MORPHTARGETS
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
#endif`,Nm=`#ifdef USE_MORPHTARGETS
	transformed *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) transformed += getMorph( gl_VertexID, i, 0 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,Um=`float faceDirection = gl_FrontFacing ? 1.0 : - 1.0;
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
vec3 nonPerturbedNormal = normal;`,Fm=`#ifdef USE_NORMALMAP_OBJECTSPACE
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
#endif`,Om=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,Bm=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,km=`#ifndef FLAT_SHADED
	vNormal = normalize( transformedNormal );
	#ifdef USE_TANGENT
		vTangent = normalize( transformedTangent );
		vBitangent = normalize( cross( vNormal, vTangent ) * tangent.w );
		#ifdef FLIP_SIDED
			vBitangent = - vBitangent;
		#endif
	#endif
#endif`,Hm=`#ifdef USE_NORMALMAP
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
#endif`,Vm=`#ifdef USE_CLEARCOAT
	vec3 clearcoatNormal = nonPerturbedNormal;
#endif`,Gm=`#ifdef USE_CLEARCOAT_NORMALMAP
	vec3 clearcoatMapN = texture2D( clearcoatNormalMap, vClearcoatNormalMapUv ).xyz * 2.0 - 1.0;
	clearcoatMapN.xy *= clearcoatNormalScale;
	clearcoatNormal = normalize( tbn2 * clearcoatMapN );
#endif`,Wm=`#ifdef USE_CLEARCOATMAP
	uniform sampler2D clearcoatMap;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform sampler2D clearcoatNormalMap;
	uniform vec2 clearcoatNormalScale;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform sampler2D clearcoatRoughnessMap;
#endif`,Xm=`#ifdef USE_IRIDESCENCEMAP
	uniform sampler2D iridescenceMap;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform sampler2D iridescenceThicknessMap;
#endif`,qm=`#ifdef OPAQUE
diffuseColor.a = 1.0;
#endif
#ifdef USE_TRANSMISSION
diffuseColor.a *= material.transmissionAlpha;
#endif
gl_FragColor = vec4( outgoingLight, diffuseColor.a );`,Ym=`vec3 packNormalToRGB( const in vec3 normal ) {
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
}`,Zm=`#ifdef PREMULTIPLIED_ALPHA
	gl_FragColor.rgb *= gl_FragColor.a;
#endif`,$m=`vec4 mvPosition = vec4( transformed, 1.0 );
#ifdef USE_BATCHING
	mvPosition = batchingMatrix * mvPosition;
#endif
#ifdef USE_INSTANCING
	mvPosition = instanceMatrix * mvPosition;
#endif
mvPosition = modelViewMatrix * mvPosition;
gl_Position = projectionMatrix * mvPosition;`,Km=`#ifdef DITHERING
	gl_FragColor.rgb = dithering( gl_FragColor.rgb );
#endif`,Jm=`#ifdef DITHERING
	vec3 dithering( vec3 color ) {
		float grid_position = rand( gl_FragCoord.xy );
		vec3 dither_shift_RGB = vec3( 0.25 / 255.0, -0.25 / 255.0, 0.25 / 255.0 );
		dither_shift_RGB = mix( 2.0 * dither_shift_RGB, -2.0 * dither_shift_RGB, grid_position );
		return color + dither_shift_RGB;
	}
#endif`,jm=`float roughnessFactor = roughness;
#ifdef USE_ROUGHNESSMAP
	vec4 texelRoughness = texture2D( roughnessMap, vRoughnessMapUv );
	roughnessFactor *= texelRoughness.g;
#endif`,Qm=`#ifdef USE_ROUGHNESSMAP
	uniform sampler2D roughnessMap;
#endif`,t0=`#if NUM_SPOT_LIGHT_COORDS > 0
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
#endif`,e0=`#if NUM_SPOT_LIGHT_COORDS > 0
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
#endif`,n0=`#if ( defined( USE_SHADOWMAP ) && ( NUM_DIR_LIGHT_SHADOWS > 0 || NUM_SUN_LIGHT_SHADOWS > 0 || NUM_POINT_LIGHT_SHADOWS > 0 ) ) || ( NUM_SPOT_LIGHT_COORDS > 0 )
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
#endif`,i0=`float getShadowMask() {
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
}`,s0=`#ifdef USE_SKINNING
	mat4 boneMatX = getBoneMatrix( skinIndex.x );
	mat4 boneMatY = getBoneMatrix( skinIndex.y );
	mat4 boneMatZ = getBoneMatrix( skinIndex.z );
	mat4 boneMatW = getBoneMatrix( skinIndex.w );
#endif`,r0=`#ifdef USE_SKINNING
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
#endif`,a0=`#ifdef USE_SKINNING
	vec4 skinVertex = bindMatrix * vec4( transformed, 1.0 );
	vec4 skinned = vec4( 0.0 );
	skinned += boneMatX * skinVertex * skinWeight.x;
	skinned += boneMatY * skinVertex * skinWeight.y;
	skinned += boneMatZ * skinVertex * skinWeight.z;
	skinned += boneMatW * skinVertex * skinWeight.w;
	transformed = ( bindMatrixInverse * skinned ).xyz;
#endif`,o0=`#ifdef USE_SKINNING
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
#endif`,l0=`float specularStrength;
#ifdef USE_SPECULARMAP
	vec4 texelSpecular = texture2D( specularMap, vSpecularMapUv );
	specularStrength = texelSpecular.r;
#else
	specularStrength = 1.0;
#endif`,c0=`#ifdef USE_SPECULARMAP
	uniform sampler2D specularMap;
#endif`,h0=`#if defined( TONE_MAPPING )
	gl_FragColor.rgb = toneMapping( gl_FragColor.rgb );
#endif`,u0=`#ifndef saturate
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
vec3 CustomToneMapping( vec3 color ) { return color; }`,d0=`#ifdef USE_TRANSMISSION
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
#endif`,f0=`#ifdef USE_TRANSMISSION
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
#endif`,p0=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
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
#endif`,m0=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
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
#endif`,g0=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
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
#endif`,x0=`#if defined( USE_ENVMAP ) || defined( DISTANCE ) || defined ( USE_SHADOWMAP ) || defined ( USE_TRANSMISSION ) || NUM_SPOT_LIGHT_COORDS > 0
	vec4 worldPosition = vec4( transformed, 1.0 );
	#ifdef USE_BATCHING
		worldPosition = batchingMatrix * worldPosition;
	#endif
	#ifdef USE_INSTANCING
		worldPosition = instanceMatrix * worldPosition;
	#endif
	worldPosition = modelMatrix * worldPosition;
#endif`,_0=`varying vec2 vUv;
uniform mat3 uvTransform;
void main() {
	vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	gl_Position = vec4( position.xy, 1.0, 1.0 );
}`,y0=`uniform sampler2D t2D;
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
}`,v0=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,b0=`#ifdef ENVMAP_TYPE_CUBE
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
}`,M0=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,S0=`uniform samplerCube tCube;
uniform float tFlip;
uniform float opacity;
varying vec3 vWorldDirection;
void main() {
	vec4 texColor = textureCube( tCube, vec3( tFlip * vWorldDirection.x, vWorldDirection.yz ) );
	gl_FragColor = texColor;
	gl_FragColor.a *= opacity;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,E0=`#include <common>
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
}`,w0=`#if DEPTH_PACKING == 3200
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
}`,T0=`#define DISTANCE
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
}`,A0=`#define DISTANCE
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
}`,R0=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
}`,C0=`uniform sampler2D tEquirect;
varying vec3 vWorldDirection;
#include <common>
void main() {
	vec3 direction = normalize( vWorldDirection );
	vec2 sampleUV = equirectUv( direction );
	gl_FragColor = texture2D( tEquirect, sampleUV );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,P0=`uniform float scale;
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
}`,I0=`uniform vec3 diffuse;
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
}`,L0=`#include <common>
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
}`,D0=`uniform vec3 diffuse;
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
}`,z0=`#define LAMBERT
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
}`,N0=`#define LAMBERT
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
}`,U0=`#define MATCAP
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
}`,F0=`#define MATCAP
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
}`,O0=`#define NORMAL
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
}`,B0=`#define NORMAL
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
}`,k0=`#define PHONG
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
}`,H0=`#define PHONG
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
}`,V0=`#define STANDARD
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
}`,G0=`#define STANDARD
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
}`,W0=`#define TOON
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
}`,X0=`#define TOON
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
}`,q0=`uniform float size;
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
}`,Y0=`uniform vec3 diffuse;
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
}`,Z0=`#include <common>
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
}`,$0=`uniform vec3 color;
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
}`,K0=`uniform float rotation;
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
}`,J0=`uniform vec3 diffuse;
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
}`,oe={alphahash_fragment:_p,alphahash_pars_fragment:yp,alphamap_fragment:vp,alphamap_pars_fragment:bp,alphatest_fragment:Mp,alphatest_pars_fragment:Sp,aomap_fragment:Ep,aomap_pars_fragment:wp,batching_pars_vertex:Tp,batching_vertex:Ap,begin_vertex:Rp,beginnormal_vertex:Cp,bsdfs:Pp,iridescence_fragment:Ip,bumpmap_pars_fragment:Lp,clipping_planes_fragment:Dp,clipping_planes_pars_fragment:zp,clipping_planes_pars_vertex:Np,clipping_planes_vertex:Up,color_fragment:Fp,color_pars_fragment:Op,color_pars_vertex:Bp,color_vertex:kp,common:Hp,cube_uv_reflection_fragment:Vp,defaultnormal_vertex:Gp,displacementmap_pars_vertex:Wp,displacementmap_vertex:Xp,emissivemap_fragment:qp,emissivemap_pars_fragment:Yp,colorspace_fragment:Zp,colorspace_pars_fragment:$p,envmap_fragment:Kp,envmap_common_pars_fragment:Jp,envmap_pars_fragment:jp,envmap_pars_vertex:Qp,envmap_physical_pars_fragment:hm,envmap_vertex:tm,fog_vertex:em,fog_pars_vertex:nm,fog_fragment:im,fog_pars_fragment:sm,gradientmap_pars_fragment:rm,lightmap_pars_fragment:am,lights_lambert_fragment:om,lights_lambert_pars_fragment:lm,lights_pars_begin:cm,lights_toon_fragment:um,lights_toon_pars_fragment:dm,lights_phong_fragment:fm,lights_phong_pars_fragment:pm,lights_physical_fragment:mm,lights_physical_pars_fragment:gm,lights_fragment_begin:xm,lights_fragment_maps:_m,lights_fragment_end:ym,lightprobes_pars_fragment:vm,logdepthbuf_fragment:bm,logdepthbuf_pars_fragment:Mm,logdepthbuf_pars_vertex:Sm,logdepthbuf_vertex:Em,map_fragment:wm,map_pars_fragment:Tm,map_particle_fragment:Am,map_particle_pars_fragment:Rm,metalnessmap_fragment:Cm,metalnessmap_pars_fragment:Pm,morphinstance_vertex:Im,morphcolor_vertex:Lm,morphnormal_vertex:Dm,morphtarget_pars_vertex:zm,morphtarget_vertex:Nm,normal_fragment_begin:Um,normal_fragment_maps:Fm,normal_pars_fragment:Om,normal_pars_vertex:Bm,normal_vertex:km,normalmap_pars_fragment:Hm,clearcoat_normal_fragment_begin:Vm,clearcoat_normal_fragment_maps:Gm,clearcoat_pars_fragment:Wm,iridescence_pars_fragment:Xm,opaque_fragment:qm,packing:Ym,premultiplied_alpha_fragment:Zm,project_vertex:$m,dithering_fragment:Km,dithering_pars_fragment:Jm,roughnessmap_fragment:jm,roughnessmap_pars_fragment:Qm,shadowmap_pars_fragment:t0,shadowmap_pars_vertex:e0,shadowmap_vertex:n0,shadowmask_pars_fragment:i0,skinbase_vertex:s0,skinning_pars_vertex:r0,skinning_vertex:a0,skinnormal_vertex:o0,specularmap_fragment:l0,specularmap_pars_fragment:c0,tonemapping_fragment:h0,tonemapping_pars_fragment:u0,transmission_fragment:d0,transmission_pars_fragment:f0,uv_pars_fragment:p0,uv_pars_vertex:m0,uv_vertex:g0,worldpos_vertex:x0,background_vert:_0,background_frag:y0,backgroundCube_vert:v0,backgroundCube_frag:b0,cube_vert:M0,cube_frag:S0,depth_vert:E0,depth_frag:w0,distance_vert:T0,distance_frag:A0,equirect_vert:R0,equirect_frag:C0,linedashed_vert:P0,linedashed_frag:I0,meshbasic_vert:L0,meshbasic_frag:D0,meshlambert_vert:z0,meshlambert_frag:N0,meshmatcap_vert:U0,meshmatcap_frag:F0,meshnormal_vert:O0,meshnormal_frag:B0,meshphong_vert:k0,meshphong_frag:H0,meshphysical_vert:V0,meshphysical_frag:G0,meshtoon_vert:W0,meshtoon_frag:X0,points_vert:q0,points_frag:Y0,shadow_vert:Z0,shadow_frag:$0,sprite_vert:K0,sprite_frag:J0},Lt={common:{diffuse:{value:new jt(16777215)},opacity:{value:1},map:{value:null},mapTransform:{value:new ee},alphaMap:{value:null},alphaMapTransform:{value:new ee},alphaTest:{value:0}},specularmap:{specularMap:{value:null},specularMapTransform:{value:new ee}},envmap:{envMap:{value:null},envMapRotation:{value:new ee},reflectivity:{value:1},ior:{value:1.5},refractionRatio:{value:.98},dfgLUT:{value:null}},aomap:{aoMap:{value:null},aoMapIntensity:{value:1},aoMapTransform:{value:new ee}},lightmap:{lightMap:{value:null},lightMapIntensity:{value:1},lightMapTransform:{value:new ee}},bumpmap:{bumpMap:{value:null},bumpMapTransform:{value:new ee},bumpScale:{value:1}},normalmap:{normalMap:{value:null},normalMapTransform:{value:new ee},normalScale:{value:new qt(1,1)}},displacementmap:{displacementMap:{value:null},displacementMapTransform:{value:new ee},displacementScale:{value:1},displacementBias:{value:0}},emissivemap:{emissiveMap:{value:null},emissiveMapTransform:{value:new ee}},metalnessmap:{metalnessMap:{value:null},metalnessMapTransform:{value:new ee}},roughnessmap:{roughnessMap:{value:null},roughnessMapTransform:{value:new ee}},gradientmap:{gradientMap:{value:null}},fog:{fogDensity:{value:25e-5},fogNear:{value:1},fogFar:{value:2e3},fogColor:{value:new jt(16777215)}},lights:{ambientLightColor:{value:[]},lightProbe:{value:[]},sunLights:{value:[],properties:{direction:{},color:{}}},sunLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},sunShadowMatrix:{value:[]},sunShadowCascade:{value:[]},directionalLights:{value:[],properties:{direction:{},color:{}}},directionalLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},directionalShadowMatrix:{value:[]},spotLights:{value:[],properties:{color:{},position:{},direction:{},distance:{},coneCos:{},penumbraCos:{},decay:{}}},spotLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},spotLightMap:{value:[]},spotLightMatrix:{value:[]},pointLights:{value:[],properties:{color:{},position:{},decay:{},distance:{}}},pointLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{},shadowCameraNear:{},shadowCameraFar:{}}},pointShadowMatrix:{value:[]},hemisphereLights:{value:[],properties:{direction:{},skyColor:{},groundColor:{}}},rectAreaLights:{value:[],properties:{color:{},position:{},width:{},height:{}}},ltc_1:{value:null},ltc_2:{value:null},probesSH:{value:null},probesMin:{value:new O},probesMax:{value:new O},probesResolution:{value:new O}},points:{diffuse:{value:new jt(16777215)},opacity:{value:1},size:{value:1},scale:{value:1},map:{value:null},alphaMap:{value:null},alphaMapTransform:{value:new ee},alphaTest:{value:0},uvTransform:{value:new ee}},sprite:{diffuse:{value:new jt(16777215)},opacity:{value:1},center:{value:new qt(.5,.5)},rotation:{value:0},map:{value:null},mapTransform:{value:new ee},alphaMap:{value:null},alphaMapTransform:{value:new ee},alphaTest:{value:0}}},Si={basic:{uniforms:pn([Lt.common,Lt.specularmap,Lt.envmap,Lt.aomap,Lt.lightmap,Lt.fog]),vertexShader:oe.meshbasic_vert,fragmentShader:oe.meshbasic_frag},lambert:{uniforms:pn([Lt.common,Lt.specularmap,Lt.envmap,Lt.aomap,Lt.lightmap,Lt.emissivemap,Lt.bumpmap,Lt.normalmap,Lt.displacementmap,Lt.fog,Lt.lights,{emissive:{value:new jt(0)},envMapIntensity:{value:1}}]),vertexShader:oe.meshlambert_vert,fragmentShader:oe.meshlambert_frag},phong:{uniforms:pn([Lt.common,Lt.specularmap,Lt.envmap,Lt.aomap,Lt.lightmap,Lt.emissivemap,Lt.bumpmap,Lt.normalmap,Lt.displacementmap,Lt.fog,Lt.lights,{emissive:{value:new jt(0)},specular:{value:new jt(1118481)},shininess:{value:30},envMapIntensity:{value:1}}]),vertexShader:oe.meshphong_vert,fragmentShader:oe.meshphong_frag},standard:{uniforms:pn([Lt.common,Lt.envmap,Lt.aomap,Lt.lightmap,Lt.emissivemap,Lt.bumpmap,Lt.normalmap,Lt.displacementmap,Lt.roughnessmap,Lt.metalnessmap,Lt.fog,Lt.lights,{emissive:{value:new jt(0)},roughness:{value:1},metalness:{value:0},envMapIntensity:{value:1}}]),vertexShader:oe.meshphysical_vert,fragmentShader:oe.meshphysical_frag},toon:{uniforms:pn([Lt.common,Lt.aomap,Lt.lightmap,Lt.emissivemap,Lt.bumpmap,Lt.normalmap,Lt.displacementmap,Lt.gradientmap,Lt.fog,Lt.lights,{emissive:{value:new jt(0)}}]),vertexShader:oe.meshtoon_vert,fragmentShader:oe.meshtoon_frag},matcap:{uniforms:pn([Lt.common,Lt.bumpmap,Lt.normalmap,Lt.displacementmap,Lt.fog,{matcap:{value:null}}]),vertexShader:oe.meshmatcap_vert,fragmentShader:oe.meshmatcap_frag},points:{uniforms:pn([Lt.points,Lt.fog]),vertexShader:oe.points_vert,fragmentShader:oe.points_frag},dashed:{uniforms:pn([Lt.common,Lt.fog,{scale:{value:1},dashSize:{value:1},totalSize:{value:2}}]),vertexShader:oe.linedashed_vert,fragmentShader:oe.linedashed_frag},depth:{uniforms:pn([Lt.common,Lt.displacementmap]),vertexShader:oe.depth_vert,fragmentShader:oe.depth_frag},normal:{uniforms:pn([Lt.common,Lt.bumpmap,Lt.normalmap,Lt.displacementmap,{opacity:{value:1}}]),vertexShader:oe.meshnormal_vert,fragmentShader:oe.meshnormal_frag},sprite:{uniforms:pn([Lt.sprite,Lt.fog]),vertexShader:oe.sprite_vert,fragmentShader:oe.sprite_frag},background:{uniforms:{uvTransform:{value:new ee},t2D:{value:null},backgroundIntensity:{value:1}},vertexShader:oe.background_vert,fragmentShader:oe.background_frag},backgroundCube:{uniforms:{envMap:{value:null},backgroundBlurriness:{value:0},backgroundIntensity:{value:1},backgroundRotation:{value:new ee}},vertexShader:oe.backgroundCube_vert,fragmentShader:oe.backgroundCube_frag},cube:{uniforms:{tCube:{value:null},tFlip:{value:-1},opacity:{value:1}},vertexShader:oe.cube_vert,fragmentShader:oe.cube_frag},equirect:{uniforms:{tEquirect:{value:null}},vertexShader:oe.equirect_vert,fragmentShader:oe.equirect_frag},distance:{uniforms:pn([Lt.common,Lt.displacementmap,{referencePosition:{value:new O},nearDistance:{value:1},farDistance:{value:1e3}}]),vertexShader:oe.distance_vert,fragmentShader:oe.distance_frag},shadow:{uniforms:pn([Lt.lights,Lt.fog,{color:{value:new jt(0)},opacity:{value:1}}]),vertexShader:oe.shadow_vert,fragmentShader:oe.shadow_frag}};Si.physical={uniforms:pn([Si.standard.uniforms,{clearcoat:{value:0},clearcoatMap:{value:null},clearcoatMapTransform:{value:new ee},clearcoatNormalMap:{value:null},clearcoatNormalMapTransform:{value:new ee},clearcoatNormalScale:{value:new qt(1,1)},clearcoatRoughness:{value:0},clearcoatRoughnessMap:{value:null},clearcoatRoughnessMapTransform:{value:new ee},dispersion:{value:0},retroreflectivity:{value:0},iridescence:{value:0},iridescenceMap:{value:null},iridescenceMapTransform:{value:new ee},iridescenceIOR:{value:1.3},iridescenceThicknessMinimum:{value:100},iridescenceThicknessMaximum:{value:400},iridescenceThicknessMap:{value:null},iridescenceThicknessMapTransform:{value:new ee},sheen:{value:0},sheenColor:{value:new jt(0)},sheenColorMap:{value:null},sheenColorMapTransform:{value:new ee},sheenRoughness:{value:1},sheenRoughnessMap:{value:null},sheenRoughnessMapTransform:{value:new ee},transmission:{value:0},transmissionMap:{value:null},transmissionMapTransform:{value:new ee},transmissionSamplerSize:{value:new qt},transmissionSamplerMap:{value:null},thickness:{value:0},thicknessMap:{value:null},thicknessMapTransform:{value:new ee},attenuationDistance:{value:0},attenuationColor:{value:new jt(0)},specularColor:{value:new jt(1,1,1)},specularColorMap:{value:null},specularColorMapTransform:{value:new ee},specularIntensity:{value:1},specularIntensityMap:{value:null},specularIntensityMapTransform:{value:new ee},anisotropyVector:{value:new qt},anisotropyMap:{value:null},anisotropyMapTransform:{value:new ee}}]),vertexShader:oe.meshphysical_vert,fragmentShader:oe.meshphysical_frag};var Rl={r:0,b:0,g:0},j0=new be,Md=new ee;Md.set(-1,0,0,0,1,0,0,0,1);function Q0(i,t,e,n,s,r){let a=new jt(0),o=s===!0?0:1,l,c,h=null,p=0,d=null;function f(S){let R=S.isScene===!0?S.background:null;if(R&&R.isTexture){let v=S.backgroundBlurriness>0;R=t.get(R,v)}return R}function _(S){let R=!1,v=f(S);v===null?m(a,o):v&&v.isColor&&(m(v,1),R=!0);let M=i.xr.getEnvironmentBlendMode();M==="additive"?e.buffers.color.setClear(0,0,0,1,r):M==="alpha-blend"&&e.buffers.color.setClear(0,0,0,0,r),(i.autoClear||R)&&(e.buffers.depth.setTest(!0),e.buffers.depth.setMask(!0),e.buffers.color.setMask(!0),i.clear(i.autoClearColor,i.autoClearDepth,i.autoClearStencil))}function b(S,R){let v=f(R);v&&(v.isCubeTexture||v.mapping===va)?(c===void 0&&(c=new Xt(new de(1,1,1),new Nn({name:"BackgroundCubeMaterial",uniforms:Hs(Si.backgroundCube.uniforms),vertexShader:Si.backgroundCube.vertexShader,fragmentShader:Si.backgroundCube.fragmentShader,side:bn,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),c.geometry.deleteAttribute("normal"),c.geometry.deleteAttribute("uv"),c.onBeforeRender=function(M,E,A){this.matrixWorld.copyPosition(A.matrixWorld)},Object.defineProperty(c.material,"envMap",{get:function(){return this.uniforms.envMap.value}}),n.update(c)),c.material.uniforms.envMap.value=v,c.material.uniforms.backgroundBlurriness.value=R.backgroundBlurriness,c.material.uniforms.backgroundIntensity.value=R.backgroundIntensity,c.material.uniforms.backgroundRotation.value.setFromMatrix4(j0.makeRotationFromEuler(R.backgroundRotation)).transpose(),v.isCubeTexture&&v.isRenderTargetTexture===!1&&c.material.uniforms.backgroundRotation.value.premultiply(Md),c.material.toneMapped=me.getTransfer(v.colorSpace)!==we,(h!==v||p!==v.version||d!==i.toneMapping)&&(c.material.needsUpdate=!0,h=v,p=v.version,d=i.toneMapping),c.layers.enableAll(),S.unshift(c,c.geometry,c.material,0,0,null)):v&&v.isTexture&&(l===void 0&&(l=new Xt(new Ns(2,2),new Nn({name:"BackgroundMaterial",uniforms:Hs(Si.background.uniforms),vertexShader:Si.background.vertexShader,fragmentShader:Si.background.fragmentShader,side:ps,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),l.geometry.deleteAttribute("normal"),Object.defineProperty(l.material,"map",{get:function(){return this.uniforms.t2D.value}}),n.update(l)),l.material.uniforms.t2D.value=v,l.material.uniforms.backgroundIntensity.value=R.backgroundIntensity,l.material.toneMapped=me.getTransfer(v.colorSpace)!==we,v.matrixAutoUpdate===!0&&v.updateMatrix(),l.material.uniforms.uvTransform.value.copy(v.matrix),(h!==v||p!==v.version||d!==i.toneMapping)&&(l.material.needsUpdate=!0,h=v,p=v.version,d=i.toneMapping),l.layers.enableAll(),S.unshift(l,l.geometry,l.material,0,0,null))}function m(S,R){S.getRGB(Rl,Kc(i)),e.buffers.color.setClear(Rl.r,Rl.g,Rl.b,R,r)}function u(){c!==void 0&&(c.geometry.dispose(),c.material.dispose(),c=void 0),l!==void 0&&(l.geometry.dispose(),l.material.dispose(),l=void 0)}return{getClearColor:function(){return a},setClearColor:function(S,R=1){a.set(S),o=R,m(a,o)},getClearAlpha:function(){return o},setClearAlpha:function(S){o=S,m(a,o)},render:_,addToRenderList:b,dispose:u}}function tg(i,t){let e=i.getParameter(i.MAX_VERTEX_ATTRIBS),n={},s=d(null),r=s,a=!1;function o(I,N,B,F,P){let V=!1,z=p(I,F,B,N);r!==z&&(r=z,c(r.object)),V=f(I,F,B,P),V&&_(I,F,B,P),P!==null&&t.update(P,i.ELEMENT_ARRAY_BUFFER),(V||a)&&(a=!1,v(I,N,B,F),P!==null&&i.bindBuffer(i.ELEMENT_ARRAY_BUFFER,t.get(P).buffer))}function l(){return i.createVertexArray()}function c(I){return i.bindVertexArray(I)}function h(I){return i.deleteVertexArray(I)}function p(I,N,B,F){let P=F.wireframe===!0,V=n[N.id];V===void 0&&(V={},n[N.id]=V);let z=I.isInstancedMesh===!0?I.id:0,X=V[z];X===void 0&&(X={},V[z]=X);let G=X[B.id];G===void 0&&(G={},X[B.id]=G);let Y=G[P];return Y===void 0&&(Y=d(l()),G[P]=Y),Y}function d(I){let N=[],B=[],F=[];for(let P=0;P<e;P++)N[P]=0,B[P]=0,F[P]=0;return{geometry:null,program:null,wireframe:!1,newAttributes:N,enabledAttributes:B,attributeDivisors:F,object:I,attributes:{},index:null}}function f(I,N,B,F){let P=r.attributes,V=N.attributes,z=0,X=B.getAttributes();for(let G in X)if(X[G].location>=0){let tt=P[G],et=V[G];if(et===void 0&&(G==="instanceMatrix"&&I.instanceMatrix&&(et=I.instanceMatrix),G==="instanceColor"&&I.instanceColor&&(et=I.instanceColor)),tt===void 0||tt.attribute!==et||et&&tt.data!==et.data)return!0;z++}return r.attributesNum!==z||r.index!==F}function _(I,N,B,F){let P={},V=N.attributes,z=0,X=B.getAttributes();for(let G in X)if(X[G].location>=0){let tt=V[G];tt===void 0&&(G==="instanceMatrix"&&I.instanceMatrix&&(tt=I.instanceMatrix),G==="instanceColor"&&I.instanceColor&&(tt=I.instanceColor));let et={};et.attribute=tt,tt&&tt.data&&(et.data=tt.data),P[G]=et,z++}r.attributes=P,r.attributesNum=z,r.index=F}function b(){let I=r.newAttributes;for(let N=0,B=I.length;N<B;N++)I[N]=0}function m(I){u(I,0)}function u(I,N){let B=r.newAttributes,F=r.enabledAttributes,P=r.attributeDivisors;B[I]=1,F[I]===0&&(i.enableVertexAttribArray(I),F[I]=1),P[I]!==N&&(i.vertexAttribDivisor(I,N),P[I]=N)}function S(){let I=r.newAttributes,N=r.enabledAttributes;for(let B=0,F=N.length;B<F;B++)N[B]!==I[B]&&(i.disableVertexAttribArray(B),N[B]=0)}function R(I,N,B,F,P,V,z){z===!0?i.vertexAttribIPointer(I,N,B,P,V):i.vertexAttribPointer(I,N,B,F,P,V)}function v(I,N,B,F){b();let P=F.attributes,V=B.getAttributes(),z=N.defaultAttributeValues;for(let X in V){let G=V[X];if(G.location>=0){let Y=P[X];if(Y===void 0&&(X==="instanceMatrix"&&I.instanceMatrix&&(Y=I.instanceMatrix),X==="instanceColor"&&I.instanceColor&&(Y=I.instanceColor)),Y!==void 0){let tt=Y.normalized,et=Y.itemSize,dt=t.get(Y);if(dt===void 0)continue;let Dt=dt.buffer,Pt=dt.type,xt=dt.bytesPerElement,q=Pt===i.INT||Pt===i.UNSIGNED_INT||Y.gpuType===Vo;if(Y.isInterleavedBufferAttribute){let it=Y.data,gt=it.stride,zt=Y.offset;if(it.isInstancedInterleavedBuffer){for(let Rt=0;Rt<G.locationSize;Rt++)u(G.location+Rt,it.meshPerAttribute);I.isInstancedMesh!==!0&&F._maxInstanceCount===void 0&&(F._maxInstanceCount=it.meshPerAttribute*it.count)}else for(let Rt=0;Rt<G.locationSize;Rt++)m(G.location+Rt);i.bindBuffer(i.ARRAY_BUFFER,Dt);for(let Rt=0;Rt<G.locationSize;Rt++)R(G.location+Rt,et/G.locationSize,Pt,tt,gt*xt,(zt+et/G.locationSize*Rt)*xt,q)}else{if(Y.isInstancedBufferAttribute){for(let it=0;it<G.locationSize;it++)u(G.location+it,Y.meshPerAttribute);I.isInstancedMesh!==!0&&F._maxInstanceCount===void 0&&(F._maxInstanceCount=Y.meshPerAttribute*Y.count)}else for(let it=0;it<G.locationSize;it++)m(G.location+it);i.bindBuffer(i.ARRAY_BUFFER,Dt);for(let it=0;it<G.locationSize;it++)R(G.location+it,et/G.locationSize,Pt,tt,et*xt,et/G.locationSize*it*xt,q)}}else if(z!==void 0){let tt=z[X];if(tt!==void 0)switch(tt.length){case 2:i.vertexAttrib2fv(G.location,tt);break;case 3:i.vertexAttrib3fv(G.location,tt);break;case 4:i.vertexAttrib4fv(G.location,tt);break;default:i.vertexAttrib1fv(G.location,tt)}}}}S()}function M(){w();for(let I in n){let N=n[I];for(let B in N){let F=N[B];for(let P in F){let V=F[P];for(let z in V)h(V[z].object),delete V[z];delete F[P]}}delete n[I]}}function E(I){if(n[I.id]===void 0)return;let N=n[I.id];for(let B in N){let F=N[B];for(let P in F){let V=F[P];for(let z in V)h(V[z].object),delete V[z];delete F[P]}}delete n[I.id]}function A(I){for(let N in n){let B=n[N];for(let F in B){let P=B[F];if(P[I.id]===void 0)continue;let V=P[I.id];for(let z in V)h(V[z].object),delete V[z];delete P[I.id]}}}function g(I){for(let N in n){let B=n[N],F=I.isInstancedMesh===!0?I.id:0,P=B[F];if(P!==void 0){for(let V in P){let z=P[V];for(let X in z)h(z[X].object),delete z[X];delete P[V]}delete B[F],Object.keys(B).length===0&&delete n[N]}}}function w(){T(),a=!0,r!==s&&(r=s,c(r.object))}function T(){s.geometry=null,s.program=null,s.wireframe=!1}return{setup:o,reset:w,resetDefaultState:T,dispose:M,releaseStatesOfGeometry:E,releaseStatesOfObject:g,releaseStatesOfProgram:A,initAttributes:b,enableAttribute:m,disableUnusedAttributes:S}}function eg(i,t,e){let n;function s(l){n=l}function r(l,c){i.drawArrays(n,l,c),e.update(c,n,1)}function a(l,c,h){h!==0&&(i.drawArraysInstanced(n,l,c,h),e.update(c,n,h))}function o(l,c,h){if(h===0)return;t.get("WEBGL_multi_draw").multiDrawArraysWEBGL(n,l,0,c,0,h);let d=0;for(let f=0;f<h;f++)d+=c[f];e.update(d,n,1)}this.setMode=s,this.render=r,this.renderInstances=a,this.renderMultiDraw=o}function ng(i,t,e,n){let s;function r(){if(s!==void 0)return s;if(t.has("EXT_texture_filter_anisotropic")===!0){let A=t.get("EXT_texture_filter_anisotropic");s=i.getParameter(A.MAX_TEXTURE_MAX_ANISOTROPY_EXT)}else s=0;return s}function a(A){return!(A!==Gn&&n.convert(A)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_FORMAT))}function o(A){let g=A===ai&&(t.has("EXT_color_buffer_half_float")||t.has("EXT_color_buffer_float"));return!(A!==An&&A!==Vn&&!g&&n.convert(A)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_TYPE))}function l(A){if(A==="highp"){if(i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.HIGH_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.HIGH_FLOAT).precision>0)return"highp";A="mediump"}return A==="mediump"&&i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.MEDIUM_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.MEDIUM_FLOAT).precision>0?"mediump":"lowp"}let c=e.precision!==void 0?e.precision:"highp",h=l(c);h!==c&&(Zt("WebGLRenderer:",c,"not supported, using",h,"instead."),c=h);let p=e.logarithmicDepthBuffer===!0,d=e.reversedDepthBuffer===!0&&t.has("EXT_clip_control");e.reversedDepthBuffer===!0&&d===!1&&Zt("WebGLRenderer: Unable to use reversed depth buffer due to missing EXT_clip_control extension. Fallback to default depth buffer.");let f=i.getParameter(i.MAX_TEXTURE_IMAGE_UNITS),_=i.getParameter(i.MAX_VERTEX_TEXTURE_IMAGE_UNITS),b=i.getParameter(i.MAX_TEXTURE_SIZE),m=i.getParameter(i.MAX_CUBE_MAP_TEXTURE_SIZE),u=i.getParameter(i.MAX_VERTEX_ATTRIBS),S=i.getParameter(i.MAX_VERTEX_UNIFORM_VECTORS),R=i.getParameter(i.MAX_VARYING_VECTORS),v=i.getParameter(i.MAX_FRAGMENT_UNIFORM_VECTORS),M=i.getParameter(i.MAX_SAMPLES),E=i.getParameter(i.SAMPLES);return{isWebGL2:!0,getMaxAnisotropy:r,getMaxPrecision:l,textureFormatReadable:a,textureTypeReadable:o,precision:c,logarithmicDepthBuffer:p,reversedDepthBuffer:d,maxTextures:f,maxVertexTextures:_,maxTextureSize:b,maxCubemapSize:m,maxAttributes:u,maxVertexUniforms:S,maxVaryings:R,maxFragmentUniforms:v,maxSamples:M,samples:E}}function ig(i){let t=this,e=null,n=0,s=!1,r=!1,a=new Dn,o=new ee,l={value:null,needsUpdate:!1};this.uniform=l,this.numPlanes=0,this.numIntersection=0,this.init=function(p,d){let f=p.length!==0||d||n!==0||s;return s=d,n=p.length,f},this.beginShadows=function(){r=!0,h(null)},this.endShadows=function(){r=!1},this.setGlobalState=function(p,d){e=h(p,d,0)},this.setState=function(p,d,f){let _=p.clippingPlanes,b=p.clipIntersection,m=p.clipShadows,u=i.get(p);if(!s||_===null||_.length===0||r&&!m)r?h(null):c();else{let S=r?0:n,R=S*4,v=u.clippingState||null;l.value=v,v=h(_,d,R,f);for(let M=0;M!==R;++M)v[M]=e[M];u.clippingState=v,this.numIntersection=b?this.numPlanes:0,this.numPlanes+=S}};function c(){l.value!==e&&(l.value=e,l.needsUpdate=n>0),t.numPlanes=n,t.numIntersection=0}function h(p,d,f,_){let b=p!==null?p.length:0,m=null;if(b!==0){if(m=l.value,_!==!0||m===null){let u=f+b*4,S=d.matrixWorldInverse;o.getNormalMatrix(S),(m===null||m.length<u)&&(m=new Float32Array(u));for(let R=0,v=f;R!==b;++R,v+=4)a.copy(p[R]).applyMatrix4(S,o),a.normal.toArray(m,v),m[v+3]=a.constant}l.value=m,l.needsUpdate=!0}return t.numPlanes=b,t.numIntersection=0,m}}var Ir=4,sg=6,rg=20,ag=256,Ra=new Er,td=new jt,rh=null,ah=0,oh=0,lh=!1,og=new O,Vs=new O,Pl=class{constructor(t){this._renderer=t,this._pingPongRenderTarget=null,this._lodMax=0,this._cubeSize=0,this._sizeLods=[],this._lodMeshes=[],this._backgroundBox=null,this._cubemapMaterial=null,this._equirectMaterial=null,this._blurMaterial=null,this._ggxMaterial=null}fromScene(t,e=0,n=.1,s=100,r={}){let{size:a=256,position:o=og}=r;rh=this._renderer.getRenderTarget(),ah=this._renderer.getActiveCubeFace(),oh=this._renderer.getActiveMipmapLevel(),lh=this._renderer.xr.enabled,this._renderer.xr.enabled=!1,this._setSize(a);let l=this._allocateTargets();return l.depthBuffer=!0,this._sceneToCubeUV(t,n,s,l,o),e>0&&this._blur(l,0,0,e),this._applyPMREM(l),this._cleanup(l),l}fromEquirectangular(t,e=null){return this._fromTexture(t,e)}fromCubemap(t,e=null){return this._fromTexture(t,e)}compileCubemapShader(){this._cubemapMaterial===null&&(this._cubemapMaterial=id(),this._compileMaterial(this._cubemapMaterial))}compileEquirectangularShader(){this._equirectMaterial===null&&(this._equirectMaterial=nd(),this._compileMaterial(this._equirectMaterial))}dispose(){this._dispose(),this._cubemapMaterial!==null&&this._cubemapMaterial.dispose(),this._equirectMaterial!==null&&this._equirectMaterial.dispose(),this._backgroundBox!==null&&(this._backgroundBox.geometry.dispose(),this._backgroundBox.material.dispose())}_setSize(t){this._lodMax=Math.floor(Math.log2(t)),this._cubeSize=Math.pow(2,this._lodMax)}_dispose(){this._blurMaterial!==null&&this._blurMaterial.dispose(),this._ggxMaterial!==null&&this._ggxMaterial.dispose(),this._pingPongRenderTarget!==null&&this._pingPongRenderTarget.dispose();for(let t=0;t<this._lodMeshes.length;t++)this._lodMeshes[t].geometry.dispose()}_cleanup(t){this._renderer.setRenderTarget(rh,ah,oh),this._renderer.xr.enabled=lh,t.scissorTest=!1,Pr(t,0,0,t.width,t.height)}_fromTexture(t,e){t.mapping===ms||t.mapping===ks?this._setSize(t.image.length===0?16:t.image[0].width||t.image[0].image.width):this._setSize(t.image.width/4),rh=this._renderer.getRenderTarget(),ah=this._renderer.getActiveCubeFace(),oh=this._renderer.getActiveMipmapLevel(),lh=this._renderer.xr.enabled,this._renderer.xr.enabled=!1;let n=e||this._allocateTargets();return this._textureToCubeUV(t,n),this._applyPMREM(n),this._cleanup(n),n}_allocateTargets(){let t=3*Math.max(this._cubeSize,112),e=4*this._cubeSize,n={magFilter:ln,minFilter:ln,generateMipmaps:!1,type:ai,format:Gn,colorSpace:ia,depthBuffer:!1},s=ed(t,e,n);if(this._pingPongRenderTarget===null||this._pingPongRenderTarget.width!==t||this._pingPongRenderTarget.height!==e){this._pingPongRenderTarget!==null&&this._dispose(),this._pingPongRenderTarget=ed(t,e,n);let{_lodMax:r}=this;({lodMeshes:this._lodMeshes,sizeLods:this._sizeLods}=lg(r)),this._blurMaterial=hg(r,t,e),this._ggxMaterial=cg(r,t,e)}return s}_compileMaterial(t){let e=new Xt(new fn,t);this._renderer.compile(e,Ra)}_sceneToCubeUV(t,e,n,s,r){let l=new Ye(90,1,e,n),c=[1,-1,1,1,1,1],h=[1,1,1,-1,-1,-1],p=this._renderer,d=p.autoClear,f=p.toneMapping;p.getClearColor(td),p.toneMapping=si,p.autoClear=!1,p.state.buffers.depth.getReversed()&&(p.setRenderTarget(s),p.clearDepth(),p.setRenderTarget(null)),this._backgroundBox===null&&(this._backgroundBox=new Xt(new de,new Te({name:"PMREM.Background",side:bn,depthWrite:!1,depthTest:!1})));let b=this._backgroundBox,m=b.material,u=!1,S=t.background;S?S.isColor&&(m.color.copy(S),t.background=null,u=!0):(m.color.copy(td),u=!0);for(let R=0;R<6;R++){let v=R%3;v===0?(l.up.set(0,c[R],0),l.position.set(r.x,r.y,r.z),l.lookAt(r.x+h[R],r.y,r.z)):v===1?(l.up.set(0,0,c[R]),l.position.set(r.x,r.y,r.z),l.lookAt(r.x,r.y+h[R],r.z)):(l.up.set(0,c[R],0),l.position.set(r.x,r.y,r.z),l.lookAt(r.x,r.y,r.z+h[R]));let M=this._cubeSize;Pr(s,v*M,R>2?M:0,M,M),p.setRenderTarget(s),u&&p.render(b,l),p.render(t,l)}p.toneMapping=f,p.autoClear=d,t.background=S}_textureToCubeUV(t,e){let n=this._renderer,s=t.mapping===ms||t.mapping===ks;s?(this._cubemapMaterial===null&&(this._cubemapMaterial=id()),this._cubemapMaterial.uniforms.flipEnvMap.value=t.isRenderTargetTexture===!1?-1:1):this._equirectMaterial===null&&(this._equirectMaterial=nd());let r=s?this._cubemapMaterial:this._equirectMaterial,a=this._lodMeshes[0];a.material=r;let o=r.uniforms;o.envMap.value=t;let l=this._cubeSize;Pr(e,0,0,3*l,2*l),n.setRenderTarget(e),n.render(a,Ra)}_applyPMREM(t){let e=this._renderer,n=e.autoClear;e.autoClear=!1;let s=this._lodMeshes.length;for(let r=1;r<s;r++)this._applyGGXFilter(t,r-1,r);e.autoClear=n}_applyGGXFilter(t,e,n){let s=this._renderer,r=this._pingPongRenderTarget,a=this._ggxMaterial,o=this._lodMeshes[n];o.material=a;let l=a.uniforms,c=n/(this._lodMeshes.length-1),h=e/(this._lodMeshes.length-1),p=Math.sqrt(c*c-h*h),d=c*1.25,f=p*d,{_lodMax:_}=this,b=this._sizeLods[n],m=3*b*(n>_-Ir?n-_+Ir:0),u=4*(this._cubeSize-b);l.envMap.value=t.texture,l.roughness.value=f,l.mipInt.value=_-e,Pr(r,m,u,3*b,2*b),s.setRenderTarget(r),s.render(o,Ra),l.envMap.value=r.texture,l.roughness.value=0,l.mipInt.value=_-n,Pr(t,m,u,3*b,2*b),s.setRenderTarget(t),s.render(o,Ra)}_blur(t,e,n,s){let r=this._pingPongRenderTarget,a=Math.min(s,Math.PI)/Math.SQRT2;this._blurPass(t,r,e,n,a),this._blurPass(r,t,n,n,a)}_blurPass(t,e,n,s,r){let a=this._renderer,o=this._blurMaterial,l=this._lodMeshes[s];l.material=o;let c=o.uniforms;c.envMap.value=t.texture,c.sigma.value=r,c.mipInt.value=this._lodMax-n;let h=this._sizeLods[s],p=3*h*(s>this._lodMax-Ir?s-this._lodMax+Ir:0),d=4*(this._cubeSize-h);Pr(e,p,d,3*h,2*h),a.setRenderTarget(e),a.render(l,Ra)}};function lg(i){let t=[],e=[],n=i,s=i-Ir+1+sg;for(let r=0;r<s;r++){let a=Math.pow(2,n);t.push(a);let o=1/(a-2),l=-o,c=1+o,h=[l,l,c,l,c,c,l,l,c,c,l,c],p=6,d=6,f=3,_=new Float32Array(f*d*p),b=new Float32Array(f*d*p);for(let u=0;u<p;u++){let S=u%3*2/3-1,R=u>2?0:-1,v=[S,R,0,S+2/3,R,0,S+2/3,R+1,0,S,R,0,S+2/3,R+1,0,S,R+1,0];_.set(v,f*d*u);for(let M=0;M<d;M++){let E=h[M*2]*2-1,A=h[M*2+1]*2-1;u===0?Vs.set(1,A,E):u===1?Vs.set(-E,1,-A):u===2?Vs.set(-E,A,1):u===3?Vs.set(-1,A,-E):u===4?Vs.set(-E,-1,A):Vs.set(E,A,-1),Vs.toArray(b,(u*d+M)*f)}}let m=new fn;m.setAttribute("position",new on(_,f)),m.setAttribute("outputDirection",new on(b,f)),e.push(new Xt(m,null)),n>Ir&&n--}return{lodMeshes:e,sizeLods:t}}function ed(i,t,e){let n=new wn(i,t,e);return n.texture.mapping=va,n.texture.name="PMREM.cubeUv",n.scissorTest=!0,n}function Pr(i,t,e,n,s){i.viewport.set(t,e,n,s),i.scissor.set(t,e,n,s)}function cg(i,t,e){return new Nn({name:"PMREMGGXConvolution",defines:{GGX_SAMPLES:ag,CUBEUV_TEXEL_WIDTH:1/t,CUBEUV_TEXEL_HEIGHT:1/e,CUBEUV_MAX_MIP:`${i}.0`},uniforms:{envMap:{value:null},roughness:{value:0},mipInt:{value:0}},vertexShader:Ll(),fragmentShader:`

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
		`,blending:bi,depthTest:!1,depthWrite:!1})}function hg(i,t,e){return new Nn({name:"SphericalGaussianBlur",defines:{SAMPLES:rg,CUBEUV_TEXEL_WIDTH:1/t,CUBEUV_TEXEL_HEIGHT:1/e,CUBEUV_MAX_MIP:`${i}.0`},uniforms:{envMap:{value:null},sigma:{value:0},mipInt:{value:0}},vertexShader:Ll(),fragmentShader:`

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
		`,blending:bi,depthTest:!1,depthWrite:!1})}function nd(){return new Nn({name:"EquirectangularToCubeUV",uniforms:{envMap:{value:null}},vertexShader:Ll(),fragmentShader:`

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
		`,blending:bi,depthTest:!1,depthWrite:!1})}function id(){return new Nn({name:"CubemapToCubeUV",uniforms:{envMap:{value:null},flipEnvMap:{value:-1}},vertexShader:Ll(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			uniform float flipEnvMap;

			varying vec3 vOutputDirection;

			uniform samplerCube envMap;

			void main() {

				gl_FragColor = textureCube( envMap, vec3( flipEnvMap * vOutputDirection.x, vOutputDirection.yz ) );

			}
		`,blending:bi,depthTest:!1,depthWrite:!1})}function Ll(){return`

		precision mediump float;
		precision mediump int;

		attribute vec3 outputDirection;

		varying vec3 vOutputDirection;

		void main() {

			vOutputDirection = outputDirection;
			gl_Position = vec4( position, 1.0 );

		}
	`}var Il=class extends wn{constructor(t=1,e={}){super(t,t,e),this.isWebGLCubeRenderTarget=!0;let n={width:t,height:t,depth:1},s=[n,n,n,n,n,n];this.texture=new ha(s),this._setTextureOptions(e),this.texture.isRenderTargetTexture=!0}fromEquirectangularTexture(t,e){this.texture.type=e.type,this.texture.colorSpace=e.colorSpace,this.texture.generateMipmaps=e.generateMipmaps,this.texture.minFilter=e.minFilter,this.texture.magFilter=e.magFilter;let n={uniforms:{tEquirect:{value:null}},vertexShader:`

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
			`},s=new de(5,5,5),r=new Nn({name:"CubemapFromEquirect",uniforms:Hs(n.uniforms),vertexShader:n.vertexShader,fragmentShader:n.fragmentShader,side:bn,blending:bi});r.uniforms.tEquirect.value=e;let a=new Xt(s,r),o=e.minFilter;return e.minFilter===gs&&(e.minFilter=ln),new Uo(1,10,this).update(t,a),e.minFilter=o,a.geometry.dispose(),a.material.dispose(),this}clear(t,e=!0,n=!0,s=!0){let r=t.getRenderTarget();for(let a=0;a<6;a++)t.setRenderTarget(this,a),t.clear(e,n,s);t.setRenderTarget(r)}};function ug(i){let t=new WeakMap,e=new WeakMap,n=null;function s(d,f=!1){return d==null?null:f?a(d):r(d)}function r(d){if(d&&d.isTexture){let f=d.mapping;if(f===Bo||f===ko)if(t.has(d)){let _=t.get(d).texture;return o(_,d.mapping)}else{let _=d.image;if(_&&_.height>0){let b=new Il(_.height);return b.fromEquirectangularTexture(i,d),t.set(d,b),d.addEventListener("dispose",c),o(b.texture,d.mapping)}else return null}}return d}function a(d){if(d&&d.isTexture){let f=d.mapping,_=f===Bo||f===ko,b=f===ms||f===ks;if(_||b){let m=e.get(d),u=m!==void 0?m.texture.pmremVersion:0;if(d.isRenderTargetTexture&&d.pmremVersion!==u)return n===null&&(n=new Pl(i)),m=_?n.fromEquirectangular(d,m):n.fromCubemap(d,m),m.texture.pmremVersion=d.pmremVersion,e.set(d,m),m.texture;if(m!==void 0)return m.texture;{let S=d.image;return _&&S&&S.height>0||b&&S&&l(S)?(n===null&&(n=new Pl(i)),m=_?n.fromEquirectangular(d):n.fromCubemap(d),m.texture.pmremVersion=d.pmremVersion,e.set(d,m),d.addEventListener("dispose",h),m.texture):null}}}return d}function o(d,f){return f===Bo?d.mapping=ms:f===ko&&(d.mapping=ks),d}function l(d){let f=0,_=6;for(let b=0;b<_;b++)d[b]!==void 0&&f++;return f===_}function c(d){let f=d.target;f.removeEventListener("dispose",c);let _=t.get(f);_!==void 0&&(t.delete(f),_.dispose())}function h(d){let f=d.target;f.removeEventListener("dispose",h);let _=e.get(f);_!==void 0&&(e.delete(f),_.dispose())}function p(){t=new WeakMap,e=new WeakMap,n!==null&&(n.dispose(),n=null)}return{get:s,dispose:p}}function dg(i){let t={};function e(n){if(t[n]!==void 0)return t[n];let s=i.getExtension(n);return t[n]=s,s}return{has:function(n){return e(n)!==null},init:function(){e("EXT_color_buffer_float"),e("WEBGL_clip_cull_distance"),e("OES_texture_float_linear"),e("EXT_color_buffer_half_float"),e("WEBGL_multisampled_render_to_texture"),e("WEBGL_render_shared_exponent")},get:function(n){let s=e(n);return s===null&&Ls("WebGLRenderer: "+n+" extension not supported."),s}}}function fg(i,t,e,n){let s={},r=new WeakMap;function a(p){let d=p.target;d.index!==null&&t.remove(d.index);for(let _ in d.attributes)t.remove(d.attributes[_]);d.removeEventListener("dispose",a),delete s[d.id];let f=r.get(d);f&&(t.remove(f),r.delete(d)),n.releaseStatesOfGeometry(d),d.isInstancedBufferGeometry===!0&&delete d._maxInstanceCount,e.memory.geometries--}function o(p,d){return s[d.id]===!0||(d.addEventListener("dispose",a),s[d.id]=!0,e.memory.geometries++),d}function l(p){let d=p.attributes;for(let f in d)t.update(d[f],i.ARRAY_BUFFER)}function c(p){let d=[],f=p.index,_=p.attributes.position,b=0;if(_===void 0)return;if(f!==null){let S=f.array;b=f.version;for(let R=0,v=S.length;R<v;R+=3){let M=S[R+0],E=S[R+1],A=S[R+2];d.push(M,E,E,A,A,M)}}else{let S=_.array;b=_.version;for(let R=0,v=S.length/3-1;R<v;R+=3){let M=R+0,E=R+1,A=R+2;d.push(M,E,E,A,A,M)}}let m=new(_.count>=65535?la:oa)(d,1);m.version=b;let u=r.get(p);u&&t.remove(u),r.set(p,m)}function h(p){let d=r.get(p);if(d){let f=p.index;f!==null&&d.version<f.version&&c(p)}else c(p);return r.get(p)}return{get:o,update:l,getWireframeAttribute:h}}function pg(i,t,e){let n;function s(p){n=p}let r,a;function o(p){r=p.type,a=p.bytesPerElement}function l(p,d){i.drawElements(n,d,r,p*a),e.update(d,n,1)}function c(p,d,f){f!==0&&(i.drawElementsInstanced(n,d,r,p*a,f),e.update(d,n,f))}function h(p,d,f){if(f===0)return;t.get("WEBGL_multi_draw").multiDrawElementsWEBGL(n,d,0,r,p,0,f);let b=0;for(let m=0;m<f;m++)b+=d[m];e.update(b,n,1)}this.setMode=s,this.setIndex=o,this.render=l,this.renderInstances=c,this.renderMultiDraw=h}function mg(i){let t={geometries:0,textures:0},e={frame:0,calls:0,triangles:0,points:0,lines:0};function n(r,a,o){switch(e.calls++,a){case i.TRIANGLES:e.triangles+=o*(r/3);break;case i.LINES:e.lines+=o*(r/2);break;case i.LINE_STRIP:e.lines+=o*(r-1);break;case i.LINE_LOOP:e.lines+=o*r;break;case i.POINTS:e.points+=o*r;break;default:$t("WebGLInfo: Unknown draw mode:",a);break}}function s(){e.calls=0,e.triangles=0,e.points=0,e.lines=0}return{memory:t,render:e,programs:null,autoReset:!0,reset:s,update:n}}function gg(i,t,e){let n=new WeakMap,s=new Oe;function r(a,o,l){let c=a.morphTargetInfluences,h=o.morphAttributes.position||o.morphAttributes.normal||o.morphAttributes.color,p=h!==void 0?h.length:0,d=n.get(o);if(d===void 0||d.count!==p){let w=function(){A.dispose(),n.delete(o),o.removeEventListener("dispose",w)};d!==void 0&&d.texture.dispose();let f=o.morphAttributes.position!==void 0,_=o.morphAttributes.normal!==void 0,b=o.morphAttributes.color!==void 0,m=o.morphAttributes.position||[],u=o.morphAttributes.normal||[],S=o.morphAttributes.color||[],R=0;f===!0&&(R=1),_===!0&&(R=2),b===!0&&(R=3);let v=o.attributes.position.count*R,M=1;v>t.maxTextureSize&&(M=Math.ceil(v/t.maxTextureSize),v=t.maxTextureSize);let E=new Float32Array(v*M*4*p),A=new aa(E,v,M,p);A.type=Vn,A.needsUpdate=!0;let g=R*4;for(let T=0;T<p;T++){let I=m[T],N=u[T],B=S[T],F=v*M*4*T;for(let P=0;P<I.count;P++){let V=P*g;f===!0&&(s.fromBufferAttribute(I,P),E[F+V+0]=s.x,E[F+V+1]=s.y,E[F+V+2]=s.z,E[F+V+3]=0),_===!0&&(s.fromBufferAttribute(N,P),E[F+V+4]=s.x,E[F+V+5]=s.y,E[F+V+6]=s.z,E[F+V+7]=0),b===!0&&(s.fromBufferAttribute(B,P),E[F+V+8]=s.x,E[F+V+9]=s.y,E[F+V+10]=s.z,E[F+V+11]=B.itemSize===4?s.w:1)}}d={count:p,texture:A,size:new qt(v,M)},n.set(o,d),o.addEventListener("dispose",w)}if(a.isInstancedMesh===!0&&a.morphTexture!==null)l.getUniforms().setValue(i,"morphTexture",a.morphTexture,e);else{let f=0;for(let b=0;b<c.length;b++)f+=c[b];let _=o.morphTargetsRelative?1:1-f;l.getUniforms().setValue(i,"morphTargetBaseInfluence",_),l.getUniforms().setValue(i,"morphTargetInfluences",c)}l.getUniforms().setValue(i,"morphTargetsTexture",d.texture,e),l.getUniforms().setValue(i,"morphTargetsTextureSize",d.size)}return{update:r}}function xg(i,t,e,n,s){let r=new WeakMap;function a(c){let h=s.render.frame,p=c.geometry,d=t.get(c,p);if(r.get(d)!==h&&(t.update(d),r.set(d,h)),c.isInstancedMesh&&(c.hasEventListener("dispose",l)===!1&&c.addEventListener("dispose",l),r.get(c)!==h&&(e.update(c.instanceMatrix,i.ARRAY_BUFFER),c.instanceColor!==null&&e.update(c.instanceColor,i.ARRAY_BUFFER),r.set(c,h))),c.isSkinnedMesh){let f=c.skeleton;r.get(f)!==h&&(f.update(),r.set(f,h))}return d}function o(){r=new WeakMap}function l(c){let h=c.target;h.removeEventListener("dispose",l),n.releaseStatesOfObject(h),e.remove(h.instanceMatrix),h.instanceColor!==null&&e.remove(h.instanceColor)}return{update:a,dispose:o}}var _g={[zc]:"LINEAR_TONE_MAPPING",[Nc]:"REINHARD_TONE_MAPPING",[Uc]:"CINEON_TONE_MAPPING",[Bs]:"ACES_FILMIC_TONE_MAPPING",[Oc]:"AGX_TONE_MAPPING",[Bc]:"NEUTRAL_TONE_MAPPING",[Fc]:"CUSTOM_TONE_MAPPING"};function yg(i,t,e,n,s,r){let a=new wn(t,e,{type:i,depthBuffer:s,stencilBuffer:r,samples:n?4:0,storeMultisampledDepthBuffer:!1,storeMultisampledStencilBuffer:!1,resolveDepthBuffer:!1,resolveStencilBuffer:!1}),o=null,l=null,c=new fn;c.setAttribute("position",new Fe([-1,3,0,-1,-1,0,3,-1,0],3)),c.setAttribute("uv",new Fe([0,2,0,0,2,0],2));let h=new So({uniforms:{tDiffuse:{value:null}},vertexShader:`
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
			}`,depthTest:!1,depthWrite:!1}),p=new Xt(c,h),d=new Er(-1,1,1,-1,0,1),f=null,_=null,b=!1,m,u=null,S=[],R=!1;this.setSize=function(v,M){a.setSize(v,M),o!==null&&o.setSize(v,M),l!==null&&l.setSize(v,M);for(let E=0;E<S.length;E++){let A=S[E];A.setSize&&A.setSize(v,M)}},this.setEffects=function(v){S=v,R=S.length>0&&S[0].isRenderPass===!0;let M=a.width,E=a.height;S.length>0&&o===null&&(o=new wn(M,E,{type:ai,depthBuffer:!1,stencilBuffer:!1}),l=new wn(M,E,{type:ai,depthBuffer:!1,stencilBuffer:!1}));for(let A=0;A<S.length;A++){let g=S[A];g.setSize&&g.setSize(M,E)}},this.begin=function(v,M){if(b||v.toneMapping===si&&S.length===0)return!1;if(u=M,M!==null){let E=M.width,A=M.height;(a.width!==E||a.height!==A)&&this.setSize(E,A)}return R===!1&&v.setRenderTarget(a),m=v.toneMapping,v.toneMapping=si,!0},this.hasRenderPass=function(){return R},this.end=function(v,M){v.toneMapping=m,b=!0;let E=a,A=o;for(let g=0;g<S.length;g++){let w=S[g];w.enabled!==!1&&(w.render(v,A,E,M),w.needsSwap!==!1&&(E=A,A=A===o?l:o))}if(f!==v.outputColorSpace||_!==v.toneMapping){f=v.outputColorSpace,_=v.toneMapping,h.defines={},me.getTransfer(f)===we&&(h.defines.SRGB_TRANSFER="");let g=_g[_];g&&(h.defines[g]=""),h.needsUpdate=!0}h.uniforms.tDiffuse.value=E.texture,v.setRenderTarget(u),v.render(p,d),u=null,b=!1},this.isCompositing=function(){return b},this.dispose=function(){a.dispose(),o!==null&&o.dispose(),l!==null&&l.dispose(),c.dispose(),h.dispose()}}var Sd=new vn,uh=new ls(1,1),Ed=new aa,wd=new vo,Td=new ha,sd=[],rd=[],ad=new Float32Array(16),od=new Float32Array(9),ld=new Float32Array(4);function zr(i,t,e){let n=i[0];if(n<=0||n>0)return i;let s=t*e,r=sd[s];if(r===void 0&&(r=new Float32Array(s),sd[s]=r),t!==0){n.toArray(r,0);for(let a=1,o=0;a!==t;++a)o+=e,i[a].toArray(r,o)}return r}function Ze(i,t){if(i.length!==t.length)return!1;for(let e=0,n=i.length;e<n;e++)if(i[e]!==t[e])return!1;return!0}function $e(i,t){for(let e=0,n=t.length;e<n;e++)i[e]=t[e]}function Dl(i,t){let e=rd[t];e===void 0&&(e=new Int32Array(t),rd[t]=e);for(let n=0;n!==t;++n)e[n]=i.allocateTextureUnit();return e}function vg(i,t){let e=this.cache;e[0]!==t&&(i.uniform1f(this.addr,t),e[0]=t)}function bg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y)&&(i.uniform2f(this.addr,t.x,t.y),e[0]=t.x,e[1]=t.y);else{if(Ze(e,t))return;i.uniform2fv(this.addr,t),$e(e,t)}}function Mg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z)&&(i.uniform3f(this.addr,t.x,t.y,t.z),e[0]=t.x,e[1]=t.y,e[2]=t.z);else if(t.r!==void 0)(e[0]!==t.r||e[1]!==t.g||e[2]!==t.b)&&(i.uniform3f(this.addr,t.r,t.g,t.b),e[0]=t.r,e[1]=t.g,e[2]=t.b);else{if(Ze(e,t))return;i.uniform3fv(this.addr,t),$e(e,t)}}function Sg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z||e[3]!==t.w)&&(i.uniform4f(this.addr,t.x,t.y,t.z,t.w),e[0]=t.x,e[1]=t.y,e[2]=t.z,e[3]=t.w);else{if(Ze(e,t))return;i.uniform4fv(this.addr,t),$e(e,t)}}function Eg(i,t){let e=this.cache,n=t.elements;if(n===void 0){if(Ze(e,t))return;i.uniformMatrix2fv(this.addr,!1,t),$e(e,t)}else{if(Ze(e,n))return;ld.set(n),i.uniformMatrix2fv(this.addr,!1,ld),$e(e,n)}}function wg(i,t){let e=this.cache,n=t.elements;if(n===void 0){if(Ze(e,t))return;i.uniformMatrix3fv(this.addr,!1,t),$e(e,t)}else{if(Ze(e,n))return;od.set(n),i.uniformMatrix3fv(this.addr,!1,od),$e(e,n)}}function Tg(i,t){let e=this.cache,n=t.elements;if(n===void 0){if(Ze(e,t))return;i.uniformMatrix4fv(this.addr,!1,t),$e(e,t)}else{if(Ze(e,n))return;ad.set(n),i.uniformMatrix4fv(this.addr,!1,ad),$e(e,n)}}function Ag(i,t){let e=this.cache;e[0]!==t&&(i.uniform1i(this.addr,t),e[0]=t)}function Rg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y)&&(i.uniform2i(this.addr,t.x,t.y),e[0]=t.x,e[1]=t.y);else{if(Ze(e,t))return;i.uniform2iv(this.addr,t),$e(e,t)}}function Cg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z)&&(i.uniform3i(this.addr,t.x,t.y,t.z),e[0]=t.x,e[1]=t.y,e[2]=t.z);else{if(Ze(e,t))return;i.uniform3iv(this.addr,t),$e(e,t)}}function Pg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z||e[3]!==t.w)&&(i.uniform4i(this.addr,t.x,t.y,t.z,t.w),e[0]=t.x,e[1]=t.y,e[2]=t.z,e[3]=t.w);else{if(Ze(e,t))return;i.uniform4iv(this.addr,t),$e(e,t)}}function Ig(i,t){let e=this.cache;e[0]!==t&&(i.uniform1ui(this.addr,t),e[0]=t)}function Lg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y)&&(i.uniform2ui(this.addr,t.x,t.y),e[0]=t.x,e[1]=t.y);else{if(Ze(e,t))return;i.uniform2uiv(this.addr,t),$e(e,t)}}function Dg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z)&&(i.uniform3ui(this.addr,t.x,t.y,t.z),e[0]=t.x,e[1]=t.y,e[2]=t.z);else{if(Ze(e,t))return;i.uniform3uiv(this.addr,t),$e(e,t)}}function zg(i,t){let e=this.cache;if(t.x!==void 0)(e[0]!==t.x||e[1]!==t.y||e[2]!==t.z||e[3]!==t.w)&&(i.uniform4ui(this.addr,t.x,t.y,t.z,t.w),e[0]=t.x,e[1]=t.y,e[2]=t.z,e[3]=t.w);else{if(Ze(e,t))return;i.uniform4uiv(this.addr,t),$e(e,t)}}function Ng(i,t,e){let n=this.cache,s=e.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s);let r;this.type===i.SAMPLER_2D_SHADOW?(uh.compareFunction=e.isReversedDepthBuffer()?Al:Tl,r=uh):r=Sd,e.setTexture2D(t||r,s)}function Ug(i,t,e){let n=this.cache,s=e.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s),e.setTexture3D(t||wd,s)}function Fg(i,t,e){let n=this.cache,s=e.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s),e.setTextureCube(t||Td,s)}function Og(i,t,e){let n=this.cache,s=e.allocateTextureUnit();n[0]!==s&&(i.uniform1i(this.addr,s),n[0]=s),e.setTexture2DArray(t||Ed,s)}function Bg(i){switch(i){case 5126:return vg;case 35664:return bg;case 35665:return Mg;case 35666:return Sg;case 35674:return Eg;case 35675:return wg;case 35676:return Tg;case 5124:case 35670:return Ag;case 35667:case 35671:return Rg;case 35668:case 35672:return Cg;case 35669:case 35673:return Pg;case 5125:return Ig;case 36294:return Lg;case 36295:return Dg;case 36296:return zg;case 35678:case 36198:case 36298:case 36306:case 35682:return Ng;case 35679:case 36299:case 36307:return Ug;case 35680:case 36300:case 36308:case 36293:return Fg;case 36289:case 36303:case 36311:case 36292:return Og}}function kg(i,t){i.uniform1fv(this.addr,t)}function Hg(i,t){let e=zr(t,this.size,2);i.uniform2fv(this.addr,e)}function Vg(i,t){let e=zr(t,this.size,3);i.uniform3fv(this.addr,e)}function Gg(i,t){let e=zr(t,this.size,4);i.uniform4fv(this.addr,e)}function Wg(i,t){let e=zr(t,this.size,4);i.uniformMatrix2fv(this.addr,!1,e)}function Xg(i,t){let e=zr(t,this.size,9);i.uniformMatrix3fv(this.addr,!1,e)}function qg(i,t){let e=zr(t,this.size,16);i.uniformMatrix4fv(this.addr,!1,e)}function Yg(i,t){i.uniform1iv(this.addr,t)}function Zg(i,t){i.uniform2iv(this.addr,t)}function $g(i,t){i.uniform3iv(this.addr,t)}function Kg(i,t){i.uniform4iv(this.addr,t)}function Jg(i,t){i.uniform1uiv(this.addr,t)}function jg(i,t){i.uniform2uiv(this.addr,t)}function Qg(i,t){i.uniform3uiv(this.addr,t)}function tx(i,t){i.uniform4uiv(this.addr,t)}function ex(i,t,e){let n=this.cache,s=t.length,r=Dl(e,s);Ze(n,r)||(i.uniform1iv(this.addr,r),$e(n,r));let a;this.type===i.SAMPLER_2D_SHADOW?a=uh:a=Sd;for(let o=0;o!==s;++o)e.setTexture2D(t[o]||a,r[o])}function nx(i,t,e){let n=this.cache,s=t.length,r=Dl(e,s);Ze(n,r)||(i.uniform1iv(this.addr,r),$e(n,r));for(let a=0;a!==s;++a)e.setTexture3D(t[a]||wd,r[a])}function ix(i,t,e){let n=this.cache,s=t.length,r=Dl(e,s);Ze(n,r)||(i.uniform1iv(this.addr,r),$e(n,r));for(let a=0;a!==s;++a)e.setTextureCube(t[a]||Td,r[a])}function sx(i,t,e){let n=this.cache,s=t.length,r=Dl(e,s);Ze(n,r)||(i.uniform1iv(this.addr,r),$e(n,r));for(let a=0;a!==s;++a)e.setTexture2DArray(t[a]||Ed,r[a])}function rx(i){switch(i){case 5126:return kg;case 35664:return Hg;case 35665:return Vg;case 35666:return Gg;case 35674:return Wg;case 35675:return Xg;case 35676:return qg;case 5124:case 35670:return Yg;case 35667:case 35671:return Zg;case 35668:case 35672:return $g;case 35669:case 35673:return Kg;case 5125:return Jg;case 36294:return jg;case 36295:return Qg;case 36296:return tx;case 35678:case 36198:case 36298:case 36306:case 35682:return ex;case 35679:case 36299:case 36307:return nx;case 35680:case 36300:case 36308:case 36293:return ix;case 36289:case 36303:case 36311:case 36292:return sx}}var dh=class{constructor(t,e,n){this.id=t,this.addr=n,this.cache=[],this.type=e.type,this.setValue=Bg(e.type)}},fh=class{constructor(t,e,n){this.id=t,this.addr=n,this.cache=[],this.type=e.type,this.size=e.size,this.setValue=rx(e.type)}},ph=class{constructor(t){this.id=t,this.seq=[],this.map={}}setValue(t,e,n){let s=this.seq;for(let r=0,a=s.length;r!==a;++r){let o=s[r];o.setValue(t,e[o.id],n)}}},ch=/(\w+)(\])?(\[|\.)?/g;function cd(i,t){i.seq.push(t),i.map[t.id]=t}function ax(i,t,e){let n=i.name,s=n.length;for(ch.lastIndex=0;;){let r=ch.exec(n),a=ch.lastIndex,o=r[1],l=r[2]==="]",c=r[3];if(l&&(o=o|0),c===void 0||c==="["&&a+2===s){cd(e,c===void 0?new dh(o,i,t):new fh(o,i,t));break}else{let p=e.map[o];p===void 0&&(p=new ph(o),cd(e,p)),e=p}}}var Lr=class{constructor(t,e){this.seq=[],this.map={};let n=t.getProgramParameter(e,t.ACTIVE_UNIFORMS);for(let a=0;a<n;++a){let o=t.getActiveUniform(e,a),l=t.getUniformLocation(e,o.name);ax(o,l,this)}let s=[],r=[];for(let a of this.seq)a.type===t.SAMPLER_2D_SHADOW||a.type===t.SAMPLER_CUBE_SHADOW||a.type===t.SAMPLER_2D_ARRAY_SHADOW?s.push(a):r.push(a);s.length>0&&(this.seq=s.concat(r))}setValue(t,e,n,s){let r=this.map[e];r!==void 0&&r.setValue(t,n,s)}setOptional(t,e,n){let s=e[n];s!==void 0&&this.setValue(t,n,s)}static upload(t,e,n,s){for(let r=0,a=e.length;r!==a;++r){let o=e[r],l=n[o.id];l.needsUpdate!==!1&&o.setValue(t,l.value,s)}}static seqWithValue(t,e){let n=[];for(let s=0,r=t.length;s!==r;++s){let a=t[s];a.id in e&&n.push(a)}return n}};function hd(i,t,e){let n=i.createShader(t);return i.shaderSource(n,e),i.compileShader(n),n}var ox=37297,lx=0;function cx(i,t){let e=i.split(`
`),n=[],s=Math.max(t-6,0),r=Math.min(t+6,e.length);for(let a=s;a<r;a++){let o=a+1;n.push(`${o===t?">":" "} ${o}: ${e[a]}`)}return n.join(`
`)}var ud=new ee;function hx(i){me._getMatrix(ud,me.workingColorSpace,i);let t=`mat3( ${ud.elements.map(e=>e.toFixed(4))} )`;switch(me.getTransfer(i)){case sa:return[t,"LinearTransferOETF"];case we:return[t,"sRGBTransferOETF"];default:return Zt("WebGLProgram: Unsupported color space: ",i),[t,"LinearTransferOETF"]}}function dd(i,t,e){let n=i.getShaderParameter(t,i.COMPILE_STATUS),r=(i.getShaderInfoLog(t)||"").trim();if(n&&r==="")return"";let a=/ERROR: 0:(\d+)/.exec(r);if(a){let o=parseInt(a[1]);return e.toUpperCase()+`

`+r+`

`+cx(i.getShaderSource(t),o)}else return r}function ux(i,t){let e=hx(t);return[`vec4 ${i}( vec4 value ) {`,`	return ${e[1]}( vec4( value.rgb * ${e[0]}, value.a ) );`,"}"].join(`
`)}var dx={[zc]:"Linear",[Nc]:"Reinhard",[Uc]:"Cineon",[Bs]:"ACESFilmic",[Oc]:"AgX",[Bc]:"Neutral",[Fc]:"Custom"};function fx(i,t){let e=dx[t];return e===void 0?(Zt("WebGLProgram: Unsupported toneMapping:",t),"vec3 "+i+"( vec3 color ) { return LinearToneMapping( color ); }"):"vec3 "+i+"( vec3 color ) { return "+e+"ToneMapping( color ); }"}var Cl=new O;function px(){me.getLuminanceCoefficients(Cl);let i=Cl.x.toFixed(4),t=Cl.y.toFixed(4),e=Cl.z.toFixed(4);return["float luminance( const in vec3 rgb ) {",`	const vec3 weights = vec3( ${i}, ${t}, ${e} );`,"	return dot( weights, rgb );","}"].join(`
`)}function mx(i){return[i.extensionClipCullDistance?"#extension GL_ANGLE_clip_cull_distance : require":"",i.extensionMultiDraw?"#extension GL_ANGLE_multi_draw : require":""].filter(Pa).join(`
`)}function gx(i){let t=[];for(let e in i){let n=i[e];n!==!1&&t.push("#define "+e+" "+n)}return t.join(`
`)}function xx(i,t){let e={},n=i.getProgramParameter(t,i.ACTIVE_ATTRIBUTES);for(let s=0;s<n;s++){let r=i.getActiveAttrib(t,s),a=r.name,o=1;r.type===i.FLOAT_MAT2&&(o=2),r.type===i.FLOAT_MAT3&&(o=3),r.type===i.FLOAT_MAT4&&(o=4),e[a]={type:r.type,location:i.getAttribLocation(t,a),locationSize:o}}return e}function Pa(i){return i!==""}function fd(i,t){let e=t.numSpotLightShadows+t.numSpotLightMaps-t.numSpotLightShadowsWithMaps;return i.replace(/NUM_SUN_LIGHTS/g,t.numSunLights).replace(/NUM_DIR_LIGHTS/g,t.numDirLights).replace(/NUM_SPOT_LIGHTS/g,t.numSpotLights).replace(/NUM_SPOT_LIGHT_MAPS/g,t.numSpotLightMaps).replace(/NUM_SPOT_LIGHT_COORDS/g,e).replace(/NUM_RECT_AREA_LIGHTS/g,t.numRectAreaLights).replace(/NUM_POINT_LIGHTS/g,t.numPointLights).replace(/NUM_HEMI_LIGHTS/g,t.numHemiLights).replace(/NUM_SUN_LIGHT_SHADOWS/g,t.numSunLightShadows).replace(/NUM_DIR_LIGHT_SHADOWS/g,t.numDirLightShadows).replace(/NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS/g,t.numSpotLightShadowsWithMaps).replace(/NUM_SPOT_LIGHT_SHADOWS/g,t.numSpotLightShadows).replace(/NUM_POINT_LIGHT_SHADOWS/g,t.numPointLightShadows)}function pd(i,t){return i.replace(/NUM_CLIPPING_PLANES/g,t.numClippingPlanes).replace(/UNION_CLIPPING_PLANES/g,t.numClippingPlanes-t.numClipIntersection)}var _x=/^[ \t]*#include +<([\w\d./]+)>/gm;function mh(i){return i.replace(_x,vx)}var yx=new Map;function vx(i,t){let e=oe[t];if(e===void 0){let n=yx.get(t);if(n!==void 0)e=oe[n],Zt('WebGLRenderer: Shader chunk "%s" has been deprecated. Use "%s" instead.',t,n);else throw new Error("THREE.WebGLProgram: Can not resolve #include <"+t+">")}return mh(e)}var bx=/#pragma unroll_loop_start\s+for\s*\(\s*int\s+i\s*=\s*(\d+)\s*;\s*i\s*<\s*(\d+)\s*;\s*i\s*\+\+\s*\)\s*{([\s\S]+?)}\s+#pragma unroll_loop_end/g;function md(i){return i.replace(bx,Mx)}function Mx(i,t,e,n){let s="";for(let r=parseInt(t);r<parseInt(e);r++)s+=n.replace(/\[\s*i\s*\]/g,"[ "+r+" ]").replace(/UNROLLED_LOOP_INDEX/g,r);return s}function gd(i){let t=`precision ${i.precision} float;
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
#define LOW_PRECISION`),t}var Sx={[Gi]:"SHADOWMAP_TYPE_PCF",[wr]:"SHADOWMAP_TYPE_VSM"};function Ex(i){return Sx[i.shadowMapType]||"SHADOWMAP_TYPE_BASIC"}var wx={[ms]:"ENVMAP_TYPE_CUBE",[ks]:"ENVMAP_TYPE_CUBE",[va]:"ENVMAP_TYPE_CUBE_UV"};function Tx(i){return i.envMap===!1?"ENVMAP_TYPE_CUBE":wx[i.envMapMode]||"ENVMAP_TYPE_CUBE"}var Ax={[ks]:"ENVMAP_MODE_REFRACTION"};function Rx(i){return i.envMap===!1?"ENVMAP_MODE_REFLECTION":Ax[i.envMapMode]||"ENVMAP_MODE_REFLECTION"}var Cx={[Dc]:"ENVMAP_BLENDING_MULTIPLY",[Du]:"ENVMAP_BLENDING_MIX",[zu]:"ENVMAP_BLENDING_ADD"};function Px(i){return i.envMap===!1?"ENVMAP_BLENDING_NONE":Cx[i.combine]||"ENVMAP_BLENDING_NONE"}function Ix(i){let t=i.envMapCubeUVHeight;if(t===null)return null;let e=Math.log2(t)-2,n=1/t;return{texelWidth:1/(3*Math.max(Math.pow(2,e),112)),texelHeight:n,maxMip:e}}function Lx(i,t,e,n){let s=i.getContext(),r=e.defines,a=e.vertexShader,o=e.fragmentShader,l=Ex(e),c=Tx(e),h=Rx(e),p=Px(e),d=Ix(e),f=mx(e),_=gx(r),b=s.createProgram(),m,u,S=e.glslVersion?"#version "+e.glslVersion+`
`:"";e.isRawShaderMaterial?(m=["#define SHADER_TYPE "+e.shaderType,"#define SHADER_NAME "+e.shaderName,_].filter(Pa).join(`
`),m.length>0&&(m+=`
`),u=["#define SHADER_TYPE "+e.shaderType,"#define SHADER_NAME "+e.shaderName,_].filter(Pa).join(`
`),u.length>0&&(u+=`
`)):(m=[gd(e),"#define SHADER_TYPE "+e.shaderType,"#define SHADER_NAME "+e.shaderName,_,e.extensionClipCullDistance?"#define USE_CLIP_DISTANCE":"",e.batching?"#define USE_BATCHING":"",e.batchingColor?"#define USE_BATCHING_COLOR":"",e.instancing?"#define USE_INSTANCING":"",e.instancingColor?"#define USE_INSTANCING_COLOR":"",e.instancingMorph?"#define USE_INSTANCING_MORPH":"",e.useFog&&e.fog?"#define USE_FOG":"",e.useFog&&e.fogExp2?"#define FOG_EXP2":"",e.map?"#define USE_MAP":"",e.envMap?"#define USE_ENVMAP":"",e.envMap?"#define "+h:"",e.lightMap?"#define USE_LIGHTMAP":"",e.aoMap?"#define USE_AOMAP":"",e.bumpMap?"#define USE_BUMPMAP":"",e.normalMap?"#define USE_NORMALMAP":"",e.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",e.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",e.displacementMap?"#define USE_DISPLACEMENTMAP":"",e.emissiveMap?"#define USE_EMISSIVEMAP":"",e.anisotropy?"#define USE_ANISOTROPY":"",e.anisotropyMap?"#define USE_ANISOTROPYMAP":"",e.clearcoatMap?"#define USE_CLEARCOATMAP":"",e.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",e.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",e.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",e.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",e.specularMap?"#define USE_SPECULARMAP":"",e.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",e.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",e.roughnessMap?"#define USE_ROUGHNESSMAP":"",e.metalnessMap?"#define USE_METALNESSMAP":"",e.alphaMap?"#define USE_ALPHAMAP":"",e.alphaHash?"#define USE_ALPHAHASH":"",e.transmission?"#define USE_TRANSMISSION":"",e.transmissionMap?"#define USE_TRANSMISSIONMAP":"",e.thicknessMap?"#define USE_THICKNESSMAP":"",e.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",e.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",e.mapUv?"#define MAP_UV "+e.mapUv:"",e.alphaMapUv?"#define ALPHAMAP_UV "+e.alphaMapUv:"",e.lightMapUv?"#define LIGHTMAP_UV "+e.lightMapUv:"",e.aoMapUv?"#define AOMAP_UV "+e.aoMapUv:"",e.emissiveMapUv?"#define EMISSIVEMAP_UV "+e.emissiveMapUv:"",e.bumpMapUv?"#define BUMPMAP_UV "+e.bumpMapUv:"",e.normalMapUv?"#define NORMALMAP_UV "+e.normalMapUv:"",e.displacementMapUv?"#define DISPLACEMENTMAP_UV "+e.displacementMapUv:"",e.metalnessMapUv?"#define METALNESSMAP_UV "+e.metalnessMapUv:"",e.roughnessMapUv?"#define ROUGHNESSMAP_UV "+e.roughnessMapUv:"",e.anisotropyMapUv?"#define ANISOTROPYMAP_UV "+e.anisotropyMapUv:"",e.clearcoatMapUv?"#define CLEARCOATMAP_UV "+e.clearcoatMapUv:"",e.clearcoatNormalMapUv?"#define CLEARCOAT_NORMALMAP_UV "+e.clearcoatNormalMapUv:"",e.clearcoatRoughnessMapUv?"#define CLEARCOAT_ROUGHNESSMAP_UV "+e.clearcoatRoughnessMapUv:"",e.iridescenceMapUv?"#define IRIDESCENCEMAP_UV "+e.iridescenceMapUv:"",e.iridescenceThicknessMapUv?"#define IRIDESCENCE_THICKNESSMAP_UV "+e.iridescenceThicknessMapUv:"",e.sheenColorMapUv?"#define SHEEN_COLORMAP_UV "+e.sheenColorMapUv:"",e.sheenRoughnessMapUv?"#define SHEEN_ROUGHNESSMAP_UV "+e.sheenRoughnessMapUv:"",e.specularMapUv?"#define SPECULARMAP_UV "+e.specularMapUv:"",e.specularColorMapUv?"#define SPECULAR_COLORMAP_UV "+e.specularColorMapUv:"",e.specularIntensityMapUv?"#define SPECULAR_INTENSITYMAP_UV "+e.specularIntensityMapUv:"",e.transmissionMapUv?"#define TRANSMISSIONMAP_UV "+e.transmissionMapUv:"",e.thicknessMapUv?"#define THICKNESSMAP_UV "+e.thicknessMapUv:"",e.vertexTangents&&e.flatShading===!1?"#define USE_TANGENT":"",e.vertexNormals?"#define HAS_NORMAL":"",e.vertexColors?"#define USE_COLOR":"",e.vertexAlphas?"#define USE_COLOR_ALPHA":"",e.vertexUv1s?"#define USE_UV1":"",e.vertexUv2s?"#define USE_UV2":"",e.vertexUv3s?"#define USE_UV3":"",e.pointsUvs?"#define USE_POINTS_UV":"",e.flatShading?"#define FLAT_SHADED":"",e.skinning?"#define USE_SKINNING":"",e.morphTargets?"#define USE_MORPHTARGETS":"",e.morphNormals&&e.flatShading===!1?"#define USE_MORPHNORMALS":"",e.morphColors?"#define USE_MORPHCOLORS":"",e.morphTargetsCount>0?"#define MORPHTARGETS_TEXTURE_STRIDE "+e.morphTextureStride:"",e.morphTargetsCount>0?"#define MORPHTARGETS_COUNT "+e.morphTargetsCount:"",e.doubleSided?"#define DOUBLE_SIDED":"",e.flipSided?"#define FLIP_SIDED":"",e.shadowMapEnabled?"#define USE_SHADOWMAP":"",e.shadowMapEnabled?"#define "+l:"",e.sizeAttenuation?"#define USE_SIZEATTENUATION":"",e.numLightProbes>0?"#define USE_LIGHT_PROBES":"",e.logarithmicDepthBuffer?"#define USE_LOGARITHMIC_DEPTH_BUFFER":"",e.reversedDepthBuffer?"#define USE_REVERSED_DEPTH_BUFFER":"","uniform mat4 modelMatrix;","uniform mat4 modelViewMatrix;","uniform mat4 projectionMatrix;","uniform mat4 viewMatrix;","uniform mat3 normalMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;","#ifdef USE_INSTANCING","	attribute mat4 instanceMatrix;","#endif","#ifdef USE_INSTANCING_COLOR","	attribute vec3 instanceColor;","#endif","#ifdef USE_INSTANCING_MORPH","	uniform sampler2D morphTexture;","#endif","attribute vec3 position;","attribute vec3 normal;","attribute vec2 uv;","#ifdef USE_UV1","	attribute vec2 uv1;","#endif","#ifdef USE_UV2","	attribute vec2 uv2;","#endif","#ifdef USE_UV3","	attribute vec2 uv3;","#endif","#ifdef USE_TANGENT","	attribute vec4 tangent;","#endif","#if defined( USE_COLOR_ALPHA )","	attribute vec4 color;","#elif defined( USE_COLOR )","	attribute vec3 color;","#endif","#ifdef USE_SKINNING","	attribute vec4 skinIndex;","	attribute vec4 skinWeight;","#endif",`
`].filter(Pa).join(`
`),u=[gd(e),"#define SHADER_TYPE "+e.shaderType,"#define SHADER_NAME "+e.shaderName,_,e.useFog&&e.fog?"#define USE_FOG":"",e.useFog&&e.fogExp2?"#define FOG_EXP2":"",e.alphaToCoverage?"#define ALPHA_TO_COVERAGE":"",e.map?"#define USE_MAP":"",e.matcap?"#define USE_MATCAP":"",e.envMap?"#define USE_ENVMAP":"",e.envMap?"#define "+c:"",e.envMap?"#define "+h:"",e.envMap?"#define "+p:"",d?"#define CUBEUV_TEXEL_WIDTH "+d.texelWidth:"",d?"#define CUBEUV_TEXEL_HEIGHT "+d.texelHeight:"",d?"#define CUBEUV_MAX_MIP "+d.maxMip+".0":"",e.lightMap?"#define USE_LIGHTMAP":"",e.aoMap?"#define USE_AOMAP":"",e.bumpMap?"#define USE_BUMPMAP":"",e.normalMap?"#define USE_NORMALMAP":"",e.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",e.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",e.packedNormalMap?"#define USE_PACKED_NORMALMAP":"",e.emissiveMap?"#define USE_EMISSIVEMAP":"",e.anisotropy?"#define USE_ANISOTROPY":"",e.anisotropyMap?"#define USE_ANISOTROPYMAP":"",e.clearcoat?"#define USE_CLEARCOAT":"",e.clearcoatMap?"#define USE_CLEARCOATMAP":"",e.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",e.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",e.dispersion?"#define USE_DISPERSION":"",e.retroreflection?"#define USE_RETROREFLECTION":"",e.iridescence?"#define USE_IRIDESCENCE":"",e.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",e.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",e.specularMap?"#define USE_SPECULARMAP":"",e.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",e.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",e.roughnessMap?"#define USE_ROUGHNESSMAP":"",e.metalnessMap?"#define USE_METALNESSMAP":"",e.alphaMap?"#define USE_ALPHAMAP":"",e.alphaTest?"#define USE_ALPHATEST":"",e.alphaHash?"#define USE_ALPHAHASH":"",e.sheen?"#define USE_SHEEN":"",e.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",e.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",e.transmission?"#define USE_TRANSMISSION":"",e.transmissionMap?"#define USE_TRANSMISSIONMAP":"",e.thicknessMap?"#define USE_THICKNESSMAP":"",e.vertexTangents&&e.flatShading===!1?"#define USE_TANGENT":"",e.vertexColors||e.instancingColor?"#define USE_COLOR":"",e.vertexAlphas||e.batchingColor?"#define USE_COLOR_ALPHA":"",e.vertexUv1s?"#define USE_UV1":"",e.vertexUv2s?"#define USE_UV2":"",e.vertexUv3s?"#define USE_UV3":"",e.pointsUvs?"#define USE_POINTS_UV":"",e.gradientMap?"#define USE_GRADIENTMAP":"",e.flatShading?"#define FLAT_SHADED":"",e.doubleSided?"#define DOUBLE_SIDED":"",e.flipSided?"#define FLIP_SIDED":"",e.shadowMapEnabled?"#define USE_SHADOWMAP":"",e.shadowMapEnabled?"#define "+l:"",e.premultipliedAlpha?"#define PREMULTIPLIED_ALPHA":"",e.numLightProbes>0?"#define USE_LIGHT_PROBES":"",e.numLightProbeGrids>0?"#define USE_LIGHT_PROBES_GRID":"",e.decodeVideoTexture?"#define DECODE_VIDEO_TEXTURE":"",e.decodeVideoTextureEmissive?"#define DECODE_VIDEO_TEXTURE_EMISSIVE":"",e.logarithmicDepthBuffer?"#define USE_LOGARITHMIC_DEPTH_BUFFER":"",e.reversedDepthBuffer?"#define USE_REVERSED_DEPTH_BUFFER":"","uniform mat4 viewMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;",e.toneMapping!==si?"#define TONE_MAPPING":"",e.toneMapping!==si?oe.tonemapping_pars_fragment:"",e.toneMapping!==si?fx("toneMapping",e.toneMapping):"",e.dithering?"#define DITHERING":"",e.opaque?"#define OPAQUE":"",oe.colorspace_pars_fragment,ux("linearToOutputTexel",e.outputColorSpace),px(),e.useDepthPacking?"#define DEPTH_PACKING "+e.depthPacking:"",`
`].filter(Pa).join(`
`)),a=mh(a),a=fd(a,e),a=pd(a,e),o=mh(o),o=fd(o,e),o=pd(o,e),a=md(a),o=md(o),e.isRawShaderMaterial!==!0&&(S=`#version 300 es
`,m=[f,"#define attribute in","#define varying out","#define texture2D texture"].join(`
`)+`
`+m,u=["#define varying in",e.glslVersion===Yc?"":"layout(location = 0) out highp vec4 pc_fragColor;",e.glslVersion===Yc?"":"#define gl_FragColor pc_fragColor","#define gl_FragDepthEXT gl_FragDepth","#define texture2D texture","#define textureCube texture","#define texture2DProj textureProj","#define texture2DLodEXT textureLod","#define texture2DProjLodEXT textureProjLod","#define textureCubeLodEXT textureLod","#define texture2DGradEXT textureGrad","#define texture2DProjGradEXT textureProjGrad","#define textureCubeGradEXT textureGrad"].join(`
`)+`
`+u);let R=S+m+a,v=S+u+o,M=hd(s,s.VERTEX_SHADER,R),E=hd(s,s.FRAGMENT_SHADER,v);s.attachShader(b,M),s.attachShader(b,E),e.index0AttributeName!==void 0?s.bindAttribLocation(b,0,e.index0AttributeName):e.hasPositionAttribute===!0&&s.bindAttribLocation(b,0,"position"),s.linkProgram(b);function A(I){if(i.debug.checkShaderErrors){let N=s.getProgramInfoLog(b)||"",B=s.getShaderInfoLog(M)||"",F=s.getShaderInfoLog(E)||"",P=N.trim(),V=B.trim(),z=F.trim(),X=!0,G=!0;if(s.getProgramParameter(b,s.LINK_STATUS)===!1)if(X=!1,typeof i.debug.onShaderError=="function")i.debug.onShaderError(s,b,M,E);else{let Y=dd(s,M,"vertex"),tt=dd(s,E,"fragment");$t("WebGLProgram: Shader Error "+s.getError()+" - VALIDATE_STATUS "+s.getProgramParameter(b,s.VALIDATE_STATUS)+`

Material Name: `+I.name+`
Material Type: `+I.type+`

Program Info Log: `+P+`
`+Y+`
`+tt)}else P!==""?Zt("WebGLProgram: Program Info Log:",P):(V===""||z==="")&&(G=!1);G&&(I.diagnostics={runnable:X,programLog:P,vertexShader:{log:V,prefix:m},fragmentShader:{log:z,prefix:u}})}s.deleteShader(M),s.deleteShader(E),g=new Lr(s,b),w=xx(s,b)}let g;this.getUniforms=function(){return g===void 0&&A(this),g};let w;this.getAttributes=function(){return w===void 0&&A(this),w};let T=e.rendererExtensionParallelShaderCompile===!1;return this.isReady=function(){return T===!1&&(T=s.getProgramParameter(b,ox)),T},this.destroy=function(){n.releaseStatesOfProgram(this),s.deleteProgram(b),this.program=void 0},this.type=e.shaderType,this.name=e.shaderName,this.id=lx++,this.cacheKey=t,this.usedTimes=1,this.program=b,this.vertexShader=M,this.fragmentShader=E,this}var Dx=0,gh=class{constructor(){this.shaderCache=new Map,this.materialCache=new Map}update(t,e,n){let s=this._getShaderCacheForMaterial(t);return s.has(e)===!1&&(s.add(e),e.usedTimes++),s.has(n)===!1&&(s.add(n),n.usedTimes++),this}remove(t){let e=this.materialCache.get(t);for(let n of e)n.usedTimes--,n.usedTimes===0&&this.shaderCache.delete(n.code);return this.materialCache.delete(t),this}getVertexShaderStage(t){return this._getShaderStage(t.vertexShader)}getFragmentShaderStage(t){return this._getShaderStage(t.fragmentShader)}dispose(){this.shaderCache.clear(),this.materialCache.clear()}_getShaderCacheForMaterial(t){let e=this.materialCache,n=e.get(t);return n===void 0&&(n=new Set,e.set(t,n)),n}_getShaderStage(t){let e=this.shaderCache,n=e.get(t);return n===void 0&&(n=new xh(t),e.set(t,n)),n}},xh=class{constructor(t){this.id=Dx++,this.code=t,this.usedTimes=0}};function zx(i){return i===_s||i===Ta||i===Aa}function Nx(i,t,e,n,s,r){let a=new _r,o=new gh,l=new Set,c=[],h=new Map,p=n.logarithmicDepthBuffer,d=n.precision,f={MeshDepthMaterial:"depth",MeshDistanceMaterial:"distance",MeshNormalMaterial:"normal",MeshBasicMaterial:"basic",MeshLambertMaterial:"lambert",MeshPhongMaterial:"phong",MeshToonMaterial:"toon",MeshStandardMaterial:"physical",MeshPhysicalMaterial:"physical",MeshMatcapMaterial:"matcap",LineBasicMaterial:"basic",LineDashedMaterial:"dashed",PointsMaterial:"points",ShadowMaterial:"shadow",SpriteMaterial:"sprite"};function _(g){return l.add(g),g===0?"uv":`uv${g}`}function b(g,w,T,I,N,B){let F=I.fog,P=N.geometry,V=g.isMeshStandardMaterial||g.isMeshLambertMaterial||g.isMeshPhongMaterial?I.environment:null,z=g.isMeshStandardMaterial||g.isMeshLambertMaterial&&!g.envMap||g.isMeshPhongMaterial&&!g.envMap,X=t.get(g.envMap||V,z),G=X&&X.mapping===va?X.image.height:null,Y=f[g.type];g.precision!==null&&(d=n.getMaxPrecision(g.precision),d!==g.precision&&Zt("WebGLProgram.getParameters:",g.precision,"not supported, using",d,"instead."));let tt=P.morphAttributes.position||P.morphAttributes.normal||P.morphAttributes.color,et=tt!==void 0?tt.length:0,dt=0;P.morphAttributes.position!==void 0&&(dt=1),P.morphAttributes.normal!==void 0&&(dt=2),P.morphAttributes.color!==void 0&&(dt=3);let Dt,Pt,xt,q;if(Y){let fe=Si[Y];Dt=fe.vertexShader,Pt=fe.fragmentShader}else{Dt=g.vertexShader,Pt=g.fragmentShader;let fe=o.getVertexShaderStage(g),ye=o.getFragmentShaderStage(g);o.update(g,fe,ye),xt=fe.id,q=ye.id}let it=i.getRenderTarget(),gt=i.state.buffers.depth.getReversed(),zt=N.isInstancedMesh===!0,Rt=N.isBatchedMesh===!0,Yt=!!g.map,Me=!!g.matcap,Qt=!!X,ne=!!g.aoMap,Kt=!!g.lightMap,te=!!g.bumpMap&&g.wireframe===!1,xe=!!g.normalMap,ze=!!g.displacementMap,Ne=!!g.emissiveMap,ge=!!g.metalnessMap,Ee=!!g.roughnessMap,W=g.anisotropy>0,Pe=g.clearcoat>0,_e=g.dispersion>0,C=g.retroreflectivity>0,x=g.iridescence>0,K=g.sheen>0,j=g.transmission>0,ot=W&&!!g.anisotropyMap,yt=Pe&&!!g.clearcoatMap,bt=Pe&&!!g.clearcoatNormalMap,at=Pe&&!!g.clearcoatRoughnessMap,lt=x&&!!g.iridescenceMap,Tt=x&&!!g.iridescenceThicknessMap,J=K&&!!g.sheenColorMap,nt=K&&!!g.sheenRoughnessMap,rt=!!g.specularMap,pt=!!g.specularColorMap,ct=!!g.specularIntensityMap,vt=j&&!!g.transmissionMap,U=j&&!!g.thicknessMap,ft=!!g.gradientMap,st=!!g.alphaMap,_t=g.alphaTest>0,Mt=!!g.alphaHash,ut=!!g.extensions,Gt=si;g.toneMapped&&(it===null||it.isXRRenderTarget===!0)&&(Gt=i.toneMapping);let kt={shaderID:Y,shaderType:g.type,shaderName:g.name,vertexShader:Dt,fragmentShader:Pt,defines:g.defines,customVertexShaderID:xt,customFragmentShaderID:q,isRawShaderMaterial:g.isRawShaderMaterial===!0,glslVersion:g.glslVersion,precision:d,batching:Rt,batchingColor:Rt&&N._colorsTexture!==null,instancing:zt,instancingColor:zt&&N.instanceColor!==null,instancingMorph:zt&&N.morphTexture!==null,outputColorSpace:it===null?i.outputColorSpace:it.isXRRenderTarget===!0?it.texture.colorSpace:me.workingColorSpace,alphaToCoverage:!!g.alphaToCoverage,map:Yt,matcap:Me,envMap:Qt,envMapMode:Qt&&X.mapping,envMapCubeUVHeight:G,aoMap:ne,lightMap:Kt,bumpMap:te,normalMap:xe,displacementMap:ze,emissiveMap:Ne,normalMapObjectSpace:xe&&g.normalMapType===Fu,normalMapTangentSpace:xe&&g.normalMapType===wl,packedNormalMap:xe&&g.normalMapType===wl&&zx(g.normalMap.format),metalnessMap:ge,roughnessMap:Ee,anisotropy:W,anisotropyMap:ot,clearcoat:Pe,clearcoatMap:yt,clearcoatNormalMap:bt,clearcoatRoughnessMap:at,dispersion:_e,retroreflection:C,iridescence:x,iridescenceMap:lt,iridescenceThicknessMap:Tt,sheen:K,sheenColorMap:J,sheenRoughnessMap:nt,specularMap:rt,specularColorMap:pt,specularIntensityMap:ct,transmission:j,transmissionMap:vt,thicknessMap:U,gradientMap:ft,opaque:g.transparent===!1&&g.blending===Tr&&g.alphaToCoverage===!1,alphaMap:st,alphaTest:_t,alphaHash:Mt,combine:g.combine,mapUv:Yt&&_(g.map.channel),aoMapUv:ne&&_(g.aoMap.channel),lightMapUv:Kt&&_(g.lightMap.channel),bumpMapUv:te&&_(g.bumpMap.channel),normalMapUv:xe&&_(g.normalMap.channel),displacementMapUv:ze&&_(g.displacementMap.channel),emissiveMapUv:Ne&&_(g.emissiveMap.channel),metalnessMapUv:ge&&_(g.metalnessMap.channel),roughnessMapUv:Ee&&_(g.roughnessMap.channel),anisotropyMapUv:ot&&_(g.anisotropyMap.channel),clearcoatMapUv:yt&&_(g.clearcoatMap.channel),clearcoatNormalMapUv:bt&&_(g.clearcoatNormalMap.channel),clearcoatRoughnessMapUv:at&&_(g.clearcoatRoughnessMap.channel),iridescenceMapUv:lt&&_(g.iridescenceMap.channel),iridescenceThicknessMapUv:Tt&&_(g.iridescenceThicknessMap.channel),sheenColorMapUv:J&&_(g.sheenColorMap.channel),sheenRoughnessMapUv:nt&&_(g.sheenRoughnessMap.channel),specularMapUv:rt&&_(g.specularMap.channel),specularColorMapUv:pt&&_(g.specularColorMap.channel),specularIntensityMapUv:ct&&_(g.specularIntensityMap.channel),transmissionMapUv:vt&&_(g.transmissionMap.channel),thicknessMapUv:U&&_(g.thicknessMap.channel),alphaMapUv:st&&_(g.alphaMap.channel),vertexTangents:!!P.attributes.tangent&&(xe||W),vertexNormals:!!P.attributes.normal,vertexColors:g.vertexColors,vertexAlphas:g.vertexColors===!0&&!!P.attributes.color&&P.attributes.color.itemSize===4,pointsUvs:N.isPoints===!0&&!!P.attributes.uv&&(Yt||st),fog:!!F,useFog:g.fog===!0,fogExp2:!!F&&F.isFogExp2,flatShading:g.wireframe===!1&&(g.flatShading===!0||P.attributes.normal===void 0&&xe===!1&&(g.isMeshLambertMaterial||g.isMeshPhongMaterial||g.isMeshStandardMaterial||g.isMeshPhysicalMaterial)),sizeAttenuation:g.sizeAttenuation===!0,logarithmicDepthBuffer:p,reversedDepthBuffer:gt,skinning:N.isSkinnedMesh===!0,hasPositionAttribute:P.attributes.position!==void 0,morphTargets:P.morphAttributes.position!==void 0,morphNormals:P.morphAttributes.normal!==void 0,morphColors:P.morphAttributes.color!==void 0,morphTargetsCount:et,morphTextureStride:dt,numSunLights:w.sun.length,numDirLights:w.directional.length,numPointLights:w.point.length,numSpotLights:w.spot.length,numSpotLightMaps:w.spotLightMap.length,numRectAreaLights:w.rectArea.length,numHemiLights:w.hemi.length,numSunLightShadows:w.sunShadowMap.length,numDirLightShadows:w.directionalShadowMap.length,numPointLightShadows:w.pointShadowMap.length,numSpotLightShadows:w.spotShadowMap.length,numSpotLightShadowsWithMaps:w.numSpotLightShadowsWithMaps,numLightProbes:w.numLightProbes,numLightProbeGrids:B.length,numClippingPlanes:r.numPlanes,numClipIntersection:r.numIntersection,dithering:g.dithering,shadowMapEnabled:i.shadowMap.enabled&&T.length>0,shadowMapType:i.shadowMap.type,toneMapping:Gt,decodeVideoTexture:Yt&&g.map.isVideoTexture===!0&&me.getTransfer(g.map.colorSpace)===we,decodeVideoTextureEmissive:Ne&&g.emissiveMap.isVideoTexture===!0&&me.getTransfer(g.emissiveMap.colorSpace)===we,premultipliedAlpha:g.premultipliedAlpha,doubleSided:g.side===vi,flipSided:g.side===bn,useDepthPacking:g.depthPacking>=0,depthPacking:g.depthPacking||0,index0AttributeName:g.index0AttributeName,extensionClipCullDistance:ut&&g.extensions.clipCullDistance===!0&&e.has("WEBGL_clip_cull_distance"),extensionMultiDraw:(ut&&g.extensions.multiDraw===!0||Rt)&&e.has("WEBGL_multi_draw"),rendererExtensionParallelShaderCompile:e.has("KHR_parallel_shader_compile"),customProgramCacheKey:g.customProgramCacheKey()};return kt.vertexUv1s=l.has(1),kt.vertexUv2s=l.has(2),kt.vertexUv3s=l.has(3),l.clear(),kt}function m(g){let w=[];if(g.shaderID?w.push(g.shaderID):(w.push(g.customVertexShaderID),w.push(g.customFragmentShaderID)),g.defines!==void 0)for(let T in g.defines)w.push(T),w.push(g.defines[T]);return g.isRawShaderMaterial===!1&&(u(w,g),S(w,g),w.push(i.outputColorSpace)),w.push(g.customProgramCacheKey),w.join()}function u(g,w){g.push(w.precision),g.push(w.outputColorSpace),g.push(w.envMapMode),g.push(w.envMapCubeUVHeight),g.push(w.mapUv),g.push(w.alphaMapUv),g.push(w.lightMapUv),g.push(w.aoMapUv),g.push(w.bumpMapUv),g.push(w.normalMapUv),g.push(w.displacementMapUv),g.push(w.emissiveMapUv),g.push(w.metalnessMapUv),g.push(w.roughnessMapUv),g.push(w.anisotropyMapUv),g.push(w.clearcoatMapUv),g.push(w.clearcoatNormalMapUv),g.push(w.clearcoatRoughnessMapUv),g.push(w.iridescenceMapUv),g.push(w.iridescenceThicknessMapUv),g.push(w.sheenColorMapUv),g.push(w.sheenRoughnessMapUv),g.push(w.specularMapUv),g.push(w.specularColorMapUv),g.push(w.specularIntensityMapUv),g.push(w.transmissionMapUv),g.push(w.thicknessMapUv),g.push(w.combine),g.push(w.fogExp2),g.push(w.sizeAttenuation),g.push(w.morphTargetsCount),g.push(w.morphAttributeCount),g.push(w.numSunLights),g.push(w.numDirLights),g.push(w.numPointLights),g.push(w.numSpotLights),g.push(w.numSpotLightMaps),g.push(w.numHemiLights),g.push(w.numRectAreaLights),g.push(w.numSunLightShadows),g.push(w.numDirLightShadows),g.push(w.numPointLightShadows),g.push(w.numSpotLightShadows),g.push(w.numSpotLightShadowsWithMaps),g.push(w.numLightProbes),g.push(w.shadowMapType),g.push(w.toneMapping),g.push(w.numClippingPlanes),g.push(w.numClipIntersection),g.push(w.depthPacking)}function S(g,w){a.disableAll(),w.instancing&&a.enable(0),w.instancingColor&&a.enable(1),w.instancingMorph&&a.enable(2),w.matcap&&a.enable(3),w.envMap&&a.enable(4),w.normalMapObjectSpace&&a.enable(5),w.normalMapTangentSpace&&a.enable(6),w.clearcoat&&a.enable(7),w.iridescence&&a.enable(8),w.alphaTest&&a.enable(9),w.vertexColors&&a.enable(10),w.vertexAlphas&&a.enable(11),w.vertexUv1s&&a.enable(12),w.vertexUv2s&&a.enable(13),w.vertexUv3s&&a.enable(14),w.vertexTangents&&a.enable(15),w.anisotropy&&a.enable(16),w.alphaHash&&a.enable(17),w.batching&&a.enable(18),w.dispersion&&a.enable(19),w.retroreflection&&a.enable(24),w.batchingColor&&a.enable(20),w.gradientMap&&a.enable(21),w.packedNormalMap&&a.enable(22),w.vertexNormals&&a.enable(23),g.push(a.mask),a.disableAll(),w.fog&&a.enable(0),w.useFog&&a.enable(1),w.flatShading&&a.enable(2),w.logarithmicDepthBuffer&&a.enable(3),w.reversedDepthBuffer&&a.enable(4),w.skinning&&a.enable(5),w.morphTargets&&a.enable(6),w.morphNormals&&a.enable(7),w.morphColors&&a.enable(8),w.premultipliedAlpha&&a.enable(9),w.shadowMapEnabled&&a.enable(10),w.doubleSided&&a.enable(11),w.flipSided&&a.enable(12),w.useDepthPacking&&a.enable(13),w.dithering&&a.enable(14),w.transmission&&a.enable(15),w.sheen&&a.enable(16),w.opaque&&a.enable(17),w.pointsUvs&&a.enable(18),w.decodeVideoTexture&&a.enable(19),w.decodeVideoTextureEmissive&&a.enable(20),w.alphaToCoverage&&a.enable(21),w.numLightProbeGrids>0&&a.enable(22),w.hasPositionAttribute&&a.enable(23),g.push(a.mask)}function R(g){let w=f[g.type],T;if(w){let I=Si[w];T=Ju.clone(I.uniforms)}else T=g.uniforms;return T}function v(g,w){let T=h.get(w);return T!==void 0?++T.usedTimes:(T=new Lx(i,w,g,s),c.push(T),h.set(w,T)),T}function M(g){if(--g.usedTimes===0){let w=c.indexOf(g);c[w]=c[c.length-1],c.pop(),h.delete(g.cacheKey),g.destroy()}}function E(g){o.remove(g)}function A(){o.dispose()}return{getParameters:b,getProgramCacheKey:m,getUniforms:R,acquireProgram:v,releaseProgram:M,releaseShaderCache:E,programs:c,dispose:A}}function Ux(){let i=new WeakMap;function t(a){return i.has(a)}function e(a){let o=i.get(a);return o===void 0&&(o={},i.set(a,o)),o}function n(a){i.delete(a)}function s(a,o,l){i.get(a)[o]=l}function r(){i=new WeakMap}return{has:t,get:e,remove:n,update:s,dispose:r}}function Fx(i,t){return i.groupOrder!==t.groupOrder?i.groupOrder-t.groupOrder:i.renderOrder!==t.renderOrder?i.renderOrder-t.renderOrder:i.material.id!==t.material.id?i.material.id-t.material.id:i.materialVariant!==t.materialVariant?i.materialVariant-t.materialVariant:i.z!==t.z?i.z-t.z:i.id-t.id}function xd(i,t){return i.groupOrder!==t.groupOrder?i.groupOrder-t.groupOrder:i.renderOrder!==t.renderOrder?i.renderOrder-t.renderOrder:i.z!==t.z?t.z-i.z:i.id-t.id}function _d(){let i=[],t=0,e=[],n=[],s=[];function r(){t=0,e.length=0,n.length=0,s.length=0}function a(d){let f=0;return d.isInstancedMesh&&(f+=2),d.isSkinnedMesh&&(f+=1),f}function o(d,f,_,b,m,u){let S=i[t];return S===void 0?(S={id:d.id,object:d,geometry:f,material:_,materialVariant:a(d),groupOrder:b,renderOrder:d.renderOrder,z:m,group:u},i[t]=S):(S.id=d.id,S.object=d,S.geometry=f,S.material=_,S.materialVariant=a(d),S.groupOrder=b,S.renderOrder=d.renderOrder,S.z=m,S.group=u),t++,S}function l(d,f,_,b,m,u,S){S.reversedDepth===!0&&(m=-m);let R=o(d,f,_,b,m,u);_.transmission>0?n.push(R):_.transparent===!0?s.push(R):e.push(R)}function c(d,f,_,b,m,u){let S=o(d,f,_,b,m,u);_.transmission>0?n.unshift(S):_.transparent===!0?s.unshift(S):e.unshift(S)}function h(d,f){e.length>1&&e.sort(d||Fx),n.length>1&&n.sort(f||xd),s.length>1&&s.sort(f||xd)}function p(){for(let d=t,f=i.length;d<f;d++){let _=i[d];if(_.id===null)break;_.id=null,_.object=null,_.geometry=null,_.material=null,_.group=null}}return{opaque:e,transmissive:n,transparent:s,init:r,push:l,unshift:c,finish:p,sort:h}}function Ox(){let i=new WeakMap;function t(n,s){let r=i.get(n),a;return r===void 0?(a=new _d,i.set(n,[a])):s>=r.length?(a=new _d,r.push(a)):a=r[s],a}function e(){i=new WeakMap}return{get:t,dispose:e}}function Bx(){let i={};return{get:function(t){if(i[t.id]!==void 0)return i[t.id];let e;switch(t.type){case"SunLight":case"DirectionalLight":e={direction:new O,color:new jt};break;case"SpotLight":e={position:new O,direction:new O,color:new jt,distance:0,coneCos:0,penumbraCos:0,decay:0};break;case"PointLight":e={position:new O,color:new jt,distance:0,decay:0};break;case"HemisphereLight":e={direction:new O,skyColor:new jt,groundColor:new jt};break;case"RectAreaLight":e={color:new jt,position:new O,halfWidth:new O,halfHeight:new O};break}return i[t.id]=e,e}}}function kx(){let i={};return{get:function(t){if(i[t.id]!==void 0)return i[t.id];let e;switch(t.type){case"SunLight":case"DirectionalLight":e={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new qt};break;case"SpotLight":e={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new qt};break;case"PointLight":e={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new qt,shadowCameraNear:1,shadowCameraFar:1e3};break}return i[t.id]=e,e}}}var Hx=0;function Vx(i,t){return(t.castShadow?2:0)-(i.castShadow?2:0)+(t.map?1:0)-(i.map?1:0)}function Gx(i){let t=new Bx,e=kx(),n={version:0,hash:{sunLength:-1,directionalLength:-1,pointLength:-1,spotLength:-1,rectAreaLength:-1,hemiLength:-1,numSunShadows:-1,numDirectionalShadows:-1,numPointShadows:-1,numSpotShadows:-1,numSpotMaps:-1,numLightProbes:-1},ambient:[0,0,0],probe:[],sun:[],sunShadow:[],sunShadowMap:[],sunShadowMatrix:[],sunShadowCascade:[],directional:[],directionalShadow:[],directionalShadowMap:[],directionalShadowMatrix:[],spot:[],spotLightMap:[],spotShadow:[],spotShadowMap:[],spotLightMatrix:[],rectArea:[],rectAreaLTC1:null,rectAreaLTC2:null,point:[],pointShadow:[],pointShadowMap:[],pointShadowMatrix:[],hemi:[],numSpotLightShadowsWithMaps:0,numLightProbes:0};for(let c=0;c<9;c++)n.probe.push(new O);let s=new O,r=new be,a=new be;function o(c){let h=0,p=0,d=0;for(let N=0;N<9;N++)n.probe[N].set(0,0,0);let f=0,_=0,b=0,m=0,u=0,S=0,R=0,v=0,M=0,E=0,A=0,g=0,w=0,T=0;c.sort(Vx);for(let N=0,B=c.length;N<B;N++){let F=c[N],P=F.color,V=F.intensity,z=F.distance,X=null;if(F.shadow&&F.shadow.map&&(F.shadow.map.texture.format===_s?X=F.shadow.map.texture:X=F.shadow.map.depthTexture||F.shadow.map.texture),F.isAmbientLight)h+=P.r*V,p+=P.g*V,d+=P.b*V;else if(F.isLightProbe){for(let G=0;G<9;G++)n.probe[G].addScaledVector(F.sh.coefficients[G],V);T++}else if(F.isSunLight){let G=t.get(F);if(G.color.copy(F.color).multiplyScalar(F.intensity),F.castShadow){let Y=F.shadow,tt=e.get(F);tt.shadowIntensity=Y.intensity,tt.shadowBias=Y.bias,tt.shadowNormalBias=Y.normalBias,tt.shadowRadius=Y.radius,tt.shadowMapSize.copy(Y.mapSize).multiply(Y.getFrameExtents()),n.sunShadow[_]=tt,n.sunShadowMap[_]=X;let et=Y.getViewportCount();for(let dt=0;dt<et;dt++)n.sunShadowMatrix[b+dt]=Y.getMatrix(dt),n.sunShadowCascade[b+dt]=Y._cascadeData[dt];b+=et,_++}n.sun[f]=G,f++}else if(F.isDirectionalLight){let G=t.get(F);if(G.color.copy(F.color).multiplyScalar(F.intensity),F.castShadow){let Y=F.shadow,tt=e.get(F);tt.shadowIntensity=Y.intensity,tt.shadowBias=Y.bias,tt.shadowNormalBias=Y.normalBias,tt.shadowRadius=Y.radius,tt.shadowMapSize=Y.mapSize,n.directionalShadow[m]=tt,n.directionalShadowMap[m]=X,n.directionalShadowMatrix[m]=F.shadow.matrix,M++}n.directional[m]=G,m++}else if(F.isSpotLight){let G=t.get(F);G.position.setFromMatrixPosition(F.matrixWorld),G.color.copy(P).multiplyScalar(V),G.distance=z,G.coneCos=Math.cos(F.angle),G.penumbraCos=Math.cos(F.angle*(1-F.penumbra)),G.decay=F.decay,n.spot[S]=G;let Y=F.shadow;if(F.map&&(n.spotLightMap[g]=F.map,g++,Y.updateMatrices(F),F.castShadow&&w++),n.spotLightMatrix[S]=Y.matrix,F.castShadow){let tt=e.get(F);tt.shadowIntensity=Y.intensity,tt.shadowBias=Y.bias,tt.shadowNormalBias=Y.normalBias,tt.shadowRadius=Y.radius,tt.shadowMapSize=Y.mapSize,n.spotShadow[S]=tt,n.spotShadowMap[S]=X,A++}S++}else if(F.isRectAreaLight){let G=t.get(F);G.color.copy(P).multiplyScalar(V),G.halfWidth.set(F.width*.5,0,0),G.halfHeight.set(0,F.height*.5,0),n.rectArea[R]=G,R++}else if(F.isPointLight){let G=t.get(F);if(G.color.copy(F.color).multiplyScalar(F.intensity),G.distance=F.distance,G.decay=F.decay,F.castShadow){let Y=F.shadow,tt=e.get(F);tt.shadowIntensity=Y.intensity,tt.shadowBias=Y.bias,tt.shadowNormalBias=Y.normalBias,tt.shadowRadius=Y.radius,tt.shadowMapSize=Y.mapSize,tt.shadowCameraNear=Y.camera.near,tt.shadowCameraFar=Y.camera.far,n.pointShadow[u]=tt,n.pointShadowMap[u]=X,n.pointShadowMatrix[u]=F.shadow.matrix,E++}n.point[u]=G,u++}else if(F.isHemisphereLight){let G=t.get(F);G.skyColor.copy(F.color).multiplyScalar(V),G.groundColor.copy(F.groundColor).multiplyScalar(V),n.hemi[v]=G,v++}}R>0&&(i.has("OES_texture_float_linear")===!0?(n.rectAreaLTC1=Lt.LTC_FLOAT_1,n.rectAreaLTC2=Lt.LTC_FLOAT_2):(n.rectAreaLTC1=Lt.LTC_HALF_1,n.rectAreaLTC2=Lt.LTC_HALF_2)),n.ambient[0]=h,n.ambient[1]=p,n.ambient[2]=d;let I=n.hash;(I.sunLength!==f||I.directionalLength!==m||I.pointLength!==u||I.spotLength!==S||I.rectAreaLength!==R||I.hemiLength!==v||I.numSunShadows!==_||I.numDirectionalShadows!==M||I.numPointShadows!==E||I.numSpotShadows!==A||I.numSpotMaps!==g||I.numLightProbes!==T)&&(n.sun.length=f,n.directional.length=m,n.spot.length=S,n.rectArea.length=R,n.point.length=u,n.hemi.length=v,n.sunShadow.length=_,n.sunShadowMap.length=_,n.sunShadowMatrix.length=b,n.sunShadowCascade.length=b,n.directionalShadow.length=M,n.directionalShadowMap.length=M,n.directionalShadowMatrix.length=M,n.pointShadow.length=E,n.pointShadowMap.length=E,n.pointShadowMatrix.length=E,n.spotShadow.length=A,n.spotShadowMap.length=A,n.spotLightMatrix.length=A+g-w,n.spotLightMap.length=g,n.numSpotLightShadowsWithMaps=w,n.numLightProbes=T,I.sunLength=f,I.directionalLength=m,I.pointLength=u,I.spotLength=S,I.rectAreaLength=R,I.hemiLength=v,I.numSunShadows=_,I.numDirectionalShadows=M,I.numPointShadows=E,I.numSpotShadows=A,I.numSpotMaps=g,I.numLightProbes=T,n.version=Hx++)}function l(c,h){let p=0,d=0,f=0,_=0,b=0,m=0,u=h.matrixWorldInverse;for(let S=0,R=c.length;S<R;S++){let v=c[S];if(v.isSunLight){let M=n.sun[p];M.direction.setFromMatrixPosition(v.matrixWorld),M.direction.transformDirection(u),p++}else if(v.isDirectionalLight){let M=n.directional[d];M.direction.setFromMatrixPosition(v.matrixWorld),s.setFromMatrixPosition(v.target.matrixWorld),M.direction.sub(s),M.direction.transformDirection(u),d++}else if(v.isSpotLight){let M=n.spot[_];M.position.setFromMatrixPosition(v.matrixWorld),M.position.applyMatrix4(u),M.direction.setFromMatrixPosition(v.matrixWorld),s.setFromMatrixPosition(v.target.matrixWorld),M.direction.sub(s),M.direction.transformDirection(u),_++}else if(v.isRectAreaLight){let M=n.rectArea[b];M.position.setFromMatrixPosition(v.matrixWorld),M.position.applyMatrix4(u),a.identity(),r.copy(v.matrixWorld),r.premultiply(u),a.extractRotation(r),M.halfWidth.set(v.width*.5,0,0),M.halfHeight.set(0,v.height*.5,0),M.halfWidth.applyMatrix4(a),M.halfHeight.applyMatrix4(a),b++}else if(v.isPointLight){let M=n.point[f];M.position.setFromMatrixPosition(v.matrixWorld),M.position.applyMatrix4(u),f++}else if(v.isHemisphereLight){let M=n.hemi[m];M.direction.setFromMatrixPosition(v.matrixWorld),M.direction.transformDirection(u),m++}}}return{setup:o,setupView:l,state:n}}function yd(i){let t=new Gx(i),e=[],n=[],s=[];function r(d){p.camera=d,e.length=0,n.length=0,s.length=0}function a(d){e.push(d)}function o(d){n.push(d)}function l(d){s.push(d)}function c(){t.setup(e)}function h(d){t.setupView(e,d)}let p={lightsArray:e,shadowsArray:n,lightProbeGridArray:s,camera:null,lights:t,transmissionRenderTarget:{},textureUnits:0};return{init:r,state:p,setupLights:c,setupLightsView:h,pushLight:a,pushShadow:o,pushLightProbeGrid:l}}function Wx(i){let t=new WeakMap;function e(s,r=0){let a=t.get(s),o;return a===void 0?(o=new yd(i),t.set(s,[o])):r>=a.length?(o=new yd(i),a.push(o)):o=a[r],o}function n(){t=new WeakMap}return{get:e,dispose:n}}var Xx=`void main() {
	gl_Position = vec4( position, 1.0 );
}`,qx=`uniform sampler2D shadow_pass;
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
}`,Yx=[new O(1,0,0),new O(-1,0,0),new O(0,1,0),new O(0,-1,0),new O(0,0,1),new O(0,0,-1)],Zx=[new O(0,-1,0),new O(0,-1,0),new O(0,0,1),new O(0,0,-1),new O(0,-1,0),new O(0,-1,0)],vd=new be,Ca=new O,hh=new O;function $x(i,t,e){let n=new br,s=new qt,r=new qt,a=new Oe,o=new Eo,l=new wo,c={},h=e.maxTextureSize,p={[ps]:bn,[bn]:ps,[vi]:vi},d=new Nn({defines:{VSM_SAMPLES:8},uniforms:{shadow_pass:{value:null},resolution:{value:new qt},radius:{value:4}},vertexShader:Xx,fragmentShader:qx}),f=d.clone();f.defines.HORIZONTAL_PASS=1;let _=new fn;_.setAttribute("position",new on(new Float32Array([-1,-1,.5,3,-1,.5,-1,3,.5]),3));let b=new Xt(_,d),m=this;this.enabled=!1,this.autoUpdate=!0,this.needsUpdate=!1,this.type=Gi;let u=this.type;this.render=function(E,A,g){if(m.enabled===!1||m.autoUpdate===!1&&m.needsUpdate===!1||E.length===0)return;this.type===pu&&(Zt("WebGLShadowMap: PCFSoftShadowMap has been removed. Using PCFShadowMap instead."),this.type=Gi);let w=i.getRenderTarget(),T=i.getActiveCubeFace(),I=i.getActiveMipmapLevel(),N=i.state;N.setBlending(bi),N.buffers.depth.getReversed()===!0?N.buffers.color.setClear(0,0,0,0):N.buffers.color.setClear(1,1,1,1),N.buffers.depth.setTest(!0),N.setScissorTest(!1);let B=u!==this.type;B&&A.traverse(function(F){F.material&&(Array.isArray(F.material)?F.material.forEach(P=>P.needsUpdate=!0):F.material.needsUpdate=!0)});for(let F=0,P=E.length;F<P;F++){let V=E[F],z=V.shadow;if(z===void 0){Zt("WebGLShadowMap:",V,"has no shadow.");continue}if(z.autoUpdate===!1&&z.needsUpdate===!1)continue;s.copy(z.mapSize);let X=z.getFrameExtents();s.multiply(X),r.copy(z.mapSize),(s.x>h||s.y>h)&&(s.x>h&&(r.x=Math.floor(h/X.x),s.x=r.x*X.x,z.mapSize.x=r.x),s.y>h&&(r.y=Math.floor(h/X.y),s.y=r.y*X.y,z.mapSize.y=r.y));let G=i.state.buffers.depth.getReversed();if(z.camera._reversedDepth=G,z.map===null||B===!0){if(z.map!==null&&(z.map.depthTexture!==null&&(z.map.depthTexture.dispose(),z.map.depthTexture=null),z.map.dispose()),this.type===wr){if(V.isPointLight){Zt("WebGLShadowMap: VSM shadow maps are not supported for PointLights. Use PCF or BasicShadowMap instead.");continue}z.map=new wn(s.x,s.y,{format:_s,type:ai,minFilter:ln,magFilter:ln,generateMipmaps:!1}),z.map.texture.name=V.name+".shadowMap",z.map.depthTexture=new ls(s.x,s.y,Vn),z.map.depthTexture.name=V.name+".shadowMapDepth",z.map.depthTexture.format=xi,z.map.depthTexture.compareFunction=null,z.map.depthTexture.minFilter=tn,z.map.depthTexture.magFilter=tn}else V.isPointLight?(z.map=new Il(s.x),z.map.depthTexture=new bo(s.x,ri)):(z.map=new wn(s.x,s.y),z.map.depthTexture=new ls(s.x,s.y,ri)),z.map.depthTexture.name=V.name+".shadowMap",z.map.depthTexture.format=xi,this.type===Gi?(z.map.depthTexture.compareFunction=G?Al:Tl,z.map.depthTexture.minFilter=ln,z.map.depthTexture.magFilter=ln):(z.map.depthTexture.compareFunction=null,z.map.depthTexture.minFilter=tn,z.map.depthTexture.magFilter=tn);z.camera.updateProjectionMatrix()}z.map.isWebGLCubeRenderTarget!==!0&&(z.map.width!==s.x||z.map.height!==s.y)&&z.map.setSize(s.x,s.y);let Y=z.map.isWebGLCubeRenderTarget?6:z.getViewportCount();V.isPointLight!==!0&&z.updateMatrices(V,g);for(let tt=0;tt<Y;tt++){let et=z.getCamera(tt);if(V.isPointLight){let dt=z.camera,Dt=z.matrix,Pt=V.distance||dt.far;Pt!==dt.far&&(dt.far=Pt,dt.updateProjectionMatrix()),Ca.setFromMatrixPosition(V.matrixWorld),dt.position.copy(Ca),hh.copy(dt.position),hh.add(Yx[tt]),dt.up.copy(Zx[tt]),dt.lookAt(hh),dt.updateMatrixWorld(),Dt.makeTranslation(-Ca.x,-Ca.y,-Ca.z),vd.multiplyMatrices(dt.projectionMatrix,dt.matrixWorldInverse),z._frustum.setFromProjectionMatrix(vd,dt.coordinateSystem,dt.reversedDepth)}if(z.map.isWebGLCubeRenderTarget)i.setRenderTarget(z.map,tt),i.clear();else{tt===0&&(i.setRenderTarget(z.map),i.clear());let dt=z.getViewport(tt);a.set(r.x*dt.x,r.y*dt.y,r.x*dt.z,r.y*dt.w),N.viewport(a)}n=z.getFrustum(tt),v(A,g,et,V,this.type)}z.isPointLightShadow!==!0&&this.type===wr&&S(z,g),z.needsUpdate=!1}u=this.type,m.needsUpdate=!1,i.setRenderTarget(w,T,I)};function S(E,A){let g=t.update(b);d.defines.VSM_SAMPLES!==E.blurSamples&&(d.defines.VSM_SAMPLES=E.blurSamples,f.defines.VSM_SAMPLES=E.blurSamples,d.needsUpdate=!0,f.needsUpdate=!0),E.mapPass===null?E.mapPass=new wn(s.x,s.y,{format:_s,type:ai}):(E.mapPass.width!==E.map.width||E.mapPass.height!==E.map.height)&&E.mapPass.setSize(E.map.width,E.map.height),d.uniforms.shadow_pass.value=E.map.depthTexture,d.uniforms.resolution.value.set(E.map.width,E.map.height),d.uniforms.radius.value=E.radius,i.setRenderTarget(E.mapPass),i.clear(),i.renderBufferDirect(A,null,g,d,b,null),f.uniforms.shadow_pass.value=E.mapPass.texture,f.uniforms.resolution.value.set(E.map.width,E.map.height),f.uniforms.radius.value=E.radius,i.setRenderTarget(E.map),i.clear(),i.renderBufferDirect(A,null,g,f,b,null)}function R(E,A,g,w){let T=null,I=g.isPointLight===!0?E.customDistanceMaterial:E.customDepthMaterial;if(I!==void 0)T=I;else if(T=g.isPointLight===!0?l:o,i.localClippingEnabled&&A.clipShadows===!0&&Array.isArray(A.clippingPlanes)&&A.clippingPlanes.length!==0||A.displacementMap&&A.displacementScale!==0||A.alphaMap&&A.alphaTest>0||A.map&&A.alphaTest>0||A.alphaToCoverage===!0){let N=T.uuid,B=A.uuid,F=c[N];F===void 0&&(F={},c[N]=F);let P=F[B];P===void 0&&(P=T.clone(),F[B]=P,A.addEventListener("dispose",M)),T=P}if(T.visible=A.visible,T.wireframe=A.wireframe,w===wr?T.side=A.shadowSide!==null?A.shadowSide:A.side:T.side=A.shadowSide!==null?A.shadowSide:p[A.side],T.alphaMap=A.alphaMap,T.alphaTest=A.alphaToCoverage===!0?.5:A.alphaTest,T.map=A.map,T.clipShadows=A.clipShadows,T.clippingPlanes=A.clippingPlanes,T.clipIntersection=A.clipIntersection,T.displacementMap=A.displacementMap,T.displacementScale=A.displacementScale,T.displacementBias=A.displacementBias,T.wireframeLinewidth=A.wireframeLinewidth,T.linewidth=A.linewidth,g.isPointLight===!0&&T.isMeshDistanceMaterial===!0){let N=i.properties.get(T);N.light=g}return T}function v(E,A,g,w,T){if(E.visible===!1)return;if(E.layers.test(A.layers)&&(E.isMesh||E.isLine||E.isPoints)&&(E.castShadow||E.receiveShadow&&T===wr)&&(!E.frustumCulled||E.intersectsFrustum(n))){E.modelViewMatrix.multiplyMatrices(g.matrixWorldInverse,E.matrixWorld);let B=t.update(E),F=E.material;if(Array.isArray(F)){let P=B.groups;for(let V=0,z=P.length;V<z;V++){let X=P[V],G=F[X.materialIndex];if(G&&G.visible){let Y=R(E,G,w,T);E.onBeforeShadow(i,E,A,g,B,Y,X),i.renderBufferDirect(g,null,B,Y,E,X),E.onAfterShadow(i,E,A,g,B,Y,X)}}}else if(F.visible){let P=R(E,F,w,T);E.onBeforeShadow(i,E,A,g,B,P,null),i.renderBufferDirect(g,null,B,P,E,null),E.onAfterShadow(i,E,A,g,B,P,null)}}let N=E.children;for(let B=0,F=N.length;B<F;B++)v(N[B],A,g,w,T)}function M(E){E.target.removeEventListener("dispose",M);for(let g in c){let w=c[g],T=E.target.uuid;T in w&&(w[T].dispose(),delete w[T])}}}function Kx(i,t){function e(){let U=!1,ft=new Oe,st=null,_t=new Oe(0,0,0,0);return{setMask:function(Mt){st!==Mt&&!U&&(i.colorMask(Mt,Mt,Mt,Mt),st=Mt)},setLocked:function(Mt){U=Mt},setClear:function(Mt,ut,Gt,kt,fe){fe===!0&&(Mt*=kt,ut*=kt,Gt*=kt),ft.set(Mt,ut,Gt,kt),_t.equals(ft)===!1&&(i.clearColor(Mt,ut,Gt,kt),_t.copy(ft))},reset:function(){U=!1,st=null,_t.set(-1,0,0,0)}}}function n(){let U=!1,ft=!1,st=null,_t=null,Mt=null;return{setReversed:function(ut){if(ft!==ut){let Gt=t.get("EXT_clip_control");ut?Gt.clipControlEXT(Gt.LOWER_LEFT_EXT,Gt.ZERO_TO_ONE_EXT):Gt.clipControlEXT(Gt.LOWER_LEFT_EXT,Gt.NEGATIVE_ONE_TO_ONE_EXT),ft=ut;let kt=Mt;Mt=null,this.setClear(kt)}},getReversed:function(){return ft},setTest:function(ut){ut?it(i.DEPTH_TEST):gt(i.DEPTH_TEST)},setMask:function(ut){st!==ut&&!U&&(i.depthMask(ut),st=ut)},setFunc:function(ut){if(ft&&(ut=$u[ut]),_t!==ut){switch(ut){case lo:i.depthFunc(i.NEVER);break;case co:i.depthFunc(i.ALWAYS);break;case ho:i.depthFunc(i.LESS);break;case fr:i.depthFunc(i.LEQUAL);break;case uo:i.depthFunc(i.EQUAL);break;case fo:i.depthFunc(i.GEQUAL);break;case po:i.depthFunc(i.GREATER);break;case mo:i.depthFunc(i.NOTEQUAL);break;default:i.depthFunc(i.LEQUAL)}_t=ut}},setLocked:function(ut){U=ut},setClear:function(ut){Mt!==ut&&(Mt=ut,ft&&(ut=1-ut),i.clearDepth(ut))},reset:function(){U=!1,st=null,_t=null,Mt=null,ft=!1}}}function s(){let U=!1,ft=null,st=null,_t=null,Mt=null,ut=null,Gt=null,kt=null,fe=null;return{setTest:function(ye){U||(ye?it(i.STENCIL_TEST):gt(i.STENCIL_TEST))},setMask:function(ye){ft!==ye&&!U&&(i.stencilMask(ye),ft=ye)},setFunc:function(ye,xn,_n){(st!==ye||_t!==xn||Mt!==_n)&&(i.stencilFunc(ye,xn,_n),st=ye,_t=xn,Mt=_n)},setOp:function(ye,xn,_n){(ut!==ye||Gt!==xn||kt!==_n)&&(i.stencilOp(ye,xn,_n),ut=ye,Gt=xn,kt=_n)},setLocked:function(ye){U=ye},setClear:function(ye){fe!==ye&&(i.clearStencil(ye),fe=ye)},reset:function(){U=!1,ft=null,st=null,_t=null,Mt=null,ut=null,Gt=null,kt=null,fe=null}}}let r=new e,a=new n,o=new s,l=new WeakMap,c=new WeakMap,h={},p={},d={},f=new WeakMap,_=[],b=null,m=!1,u=null,S=null,R=null,v=null,M=null,E=null,A=null,g=new jt(0,0,0),w=0,T=!1,I=null,N=null,B=null,F=null,P=null,V=i.getParameter(i.MAX_COMBINED_TEXTURE_IMAGE_UNITS),z=!1,X=0,G=i.getParameter(i.VERSION);G.indexOf("WebGL")!==-1?(X=parseFloat(/^WebGL (\d)/.exec(G)[1]),z=X>=1):G.indexOf("OpenGL ES")!==-1&&(X=parseFloat(/^OpenGL ES (\d)/.exec(G)[1]),z=X>=2);let Y=null,tt={},et=i.getParameter(i.SCISSOR_BOX),dt=i.getParameter(i.VIEWPORT),Dt=new Oe().fromArray(et),Pt=new Oe().fromArray(dt);function xt(U,ft,st,_t){let Mt=new Uint8Array(4),ut=i.createTexture();i.bindTexture(U,ut),i.texParameteri(U,i.TEXTURE_MIN_FILTER,i.NEAREST),i.texParameteri(U,i.TEXTURE_MAG_FILTER,i.NEAREST);for(let Gt=0;Gt<st;Gt++)U===i.TEXTURE_3D||U===i.TEXTURE_2D_ARRAY?i.texImage3D(ft,0,i.RGBA,1,1,_t,0,i.RGBA,i.UNSIGNED_BYTE,Mt):i.texImage2D(ft+Gt,0,i.RGBA,1,1,0,i.RGBA,i.UNSIGNED_BYTE,Mt);return ut}let q={};q[i.TEXTURE_2D]=xt(i.TEXTURE_2D,i.TEXTURE_2D,1),q[i.TEXTURE_CUBE_MAP]=xt(i.TEXTURE_CUBE_MAP,i.TEXTURE_CUBE_MAP_POSITIVE_X,6),q[i.TEXTURE_2D_ARRAY]=xt(i.TEXTURE_2D_ARRAY,i.TEXTURE_2D_ARRAY,1,1),q[i.TEXTURE_3D]=xt(i.TEXTURE_3D,i.TEXTURE_3D,1,1),r.setClear(0,0,0,1),a.setClear(1),o.setClear(0),it(i.DEPTH_TEST),a.setFunc(fr),te(!1),xe(Ac),it(i.CULL_FACE),ne(bi);function it(U){h[U]!==!0&&(i.enable(U),h[U]=!0)}function gt(U){h[U]!==!1&&(i.disable(U),h[U]=!1)}function zt(U,ft){return d[U]!==ft?(i.bindFramebuffer(U,ft),d[U]=ft,U===i.DRAW_FRAMEBUFFER&&(d[i.FRAMEBUFFER]=ft),U===i.FRAMEBUFFER&&(d[i.DRAW_FRAMEBUFFER]=ft),!0):!1}function Rt(U,ft){let st=_,_t=!1;if(U){st=f.get(ft),st===void 0&&(st=[],f.set(ft,st));let Mt=U.textures;if(st.length!==Mt.length||st[0]!==i.COLOR_ATTACHMENT0){for(let ut=0,Gt=Mt.length;ut<Gt;ut++)st[ut]=i.COLOR_ATTACHMENT0+ut;st.length=Mt.length,_t=!0}}else st[0]!==i.BACK&&(st[0]=i.BACK,_t=!0);_t&&i.drawBuffers(st)}function Yt(U){return b!==U?(i.useProgram(U),b=U,!0):!1}let Me={[Os]:i.FUNC_ADD,[gu]:i.FUNC_SUBTRACT,[xu]:i.FUNC_REVERSE_SUBTRACT};Me[_u]=i.MIN,Me[yu]=i.MAX;let Qt={[vu]:i.ZERO,[bu]:i.ONE,[Mu]:i.SRC_COLOR,[Ic]:i.SRC_ALPHA,[Ru]:i.SRC_ALPHA_SATURATE,[Tu]:i.DST_COLOR,[Eu]:i.DST_ALPHA,[Su]:i.ONE_MINUS_SRC_COLOR,[Lc]:i.ONE_MINUS_SRC_ALPHA,[Au]:i.ONE_MINUS_DST_COLOR,[wu]:i.ONE_MINUS_DST_ALPHA,[Cu]:i.CONSTANT_COLOR,[Pu]:i.ONE_MINUS_CONSTANT_COLOR,[Iu]:i.CONSTANT_ALPHA,[Lu]:i.ONE_MINUS_CONSTANT_ALPHA};function ne(U,ft,st,_t,Mt,ut,Gt,kt,fe,ye){if(U===bi){m===!0&&(gt(i.BLEND),m=!1);return}if(m===!1&&(it(i.BLEND),m=!0),U!==mu){if(U!==u||ye!==T){if((S!==Os||M!==Os)&&(i.blendEquation(i.FUNC_ADD),S=Os,M=Os),ye)switch(U){case Tr:i.blendFuncSeparate(i.ONE,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case Rc:i.blendFunc(i.ONE,i.ONE);break;case Cc:i.blendFuncSeparate(i.ZERO,i.ONE_MINUS_SRC_COLOR,i.ZERO,i.ONE);break;case Pc:i.blendFuncSeparate(i.DST_COLOR,i.ONE_MINUS_SRC_ALPHA,i.ZERO,i.ONE);break;default:$t("WebGLState: Invalid blending: ",U);break}else switch(U){case Tr:i.blendFuncSeparate(i.SRC_ALPHA,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case Rc:i.blendFuncSeparate(i.SRC_ALPHA,i.ONE,i.ONE,i.ONE);break;case Cc:$t("WebGLState: SubtractiveBlending requires material.premultipliedAlpha = true");break;case Pc:$t("WebGLState: MultiplyBlending requires material.premultipliedAlpha = true");break;default:$t("WebGLState: Invalid blending: ",U);break}R=null,v=null,E=null,A=null,g.set(0,0,0),w=0,u=U,T=ye}return}Mt=Mt||ft,ut=ut||st,Gt=Gt||_t,(ft!==S||Mt!==M)&&(i.blendEquationSeparate(Me[ft],Me[Mt]),S=ft,M=Mt),(st!==R||_t!==v||ut!==E||Gt!==A)&&(i.blendFuncSeparate(Qt[st],Qt[_t],Qt[ut],Qt[Gt]),R=st,v=_t,E=ut,A=Gt),(kt.equals(g)===!1||fe!==w)&&(i.blendColor(kt.r,kt.g,kt.b,fe),g.copy(kt),w=fe),u=U,T=!1}function Kt(U,ft){U.side===vi?gt(i.CULL_FACE):it(i.CULL_FACE);let st=U.side===bn;ft&&(st=!st),te(st),U.blending===Tr&&U.transparent===!1?ne(bi):ne(U.blending,U.blendEquation,U.blendSrc,U.blendDst,U.blendEquationAlpha,U.blendSrcAlpha,U.blendDstAlpha,U.blendColor,U.blendAlpha,U.premultipliedAlpha),a.setFunc(U.depthFunc),a.setTest(U.depthTest),a.setMask(U.depthWrite),r.setMask(U.colorWrite);let _t=U.stencilWrite;o.setTest(_t),_t&&(o.setMask(U.stencilWriteMask),o.setFunc(U.stencilFunc,U.stencilRef,U.stencilFuncMask),o.setOp(U.stencilFail,U.stencilZFail,U.stencilZPass)),Ne(U.polygonOffset,U.polygonOffsetFactor,U.polygonOffsetUnits),U.alphaToCoverage===!0?it(i.SAMPLE_ALPHA_TO_COVERAGE):gt(i.SAMPLE_ALPHA_TO_COVERAGE)}function te(U){I!==U&&(U?i.frontFace(i.CW):i.frontFace(i.CCW),I=U)}function xe(U){U!==du?(it(i.CULL_FACE),U!==N&&(U===Ac?i.cullFace(i.BACK):U===fu?i.cullFace(i.FRONT):i.cullFace(i.FRONT_AND_BACK))):gt(i.CULL_FACE),N=U}function ze(U){U!==B&&(z&&i.lineWidth(U),B=U)}function Ne(U,ft,st){U?(it(i.POLYGON_OFFSET_FILL),(F!==ft||P!==st)&&(F=ft,P=st,a.getReversed()&&(ft=-ft),i.polygonOffset(ft,st))):gt(i.POLYGON_OFFSET_FILL)}function ge(U){U?it(i.SCISSOR_TEST):gt(i.SCISSOR_TEST)}function Ee(U){U===void 0&&(U=i.TEXTURE0+V-1),Y!==U&&(i.activeTexture(U),Y=U)}function W(U,ft,st){st===void 0&&(Y===null?st=i.TEXTURE0+V-1:st=Y);let _t=tt[st];_t===void 0&&(_t={type:void 0,texture:void 0},tt[st]=_t),(_t.type!==U||_t.texture!==ft)&&(Y!==st&&(i.activeTexture(st),Y=st),i.bindTexture(U,ft||q[U]),_t.type=U,_t.texture=ft)}function Pe(){let U=tt[Y];U!==void 0&&U.type!==void 0&&(i.bindTexture(U.type,null),U.type=void 0,U.texture=void 0)}function _e(){try{i.compressedTexImage2D(...arguments)}catch(U){$t("WebGLState:",U)}}function C(){try{i.compressedTexImage3D(...arguments)}catch(U){$t("WebGLState:",U)}}function x(){try{i.texSubImage2D(...arguments)}catch(U){$t("WebGLState:",U)}}function K(){try{i.texSubImage3D(...arguments)}catch(U){$t("WebGLState:",U)}}function j(){try{i.compressedTexSubImage2D(...arguments)}catch(U){$t("WebGLState:",U)}}function ot(){try{i.compressedTexSubImage3D(...arguments)}catch(U){$t("WebGLState:",U)}}function yt(){try{i.texStorage2D(...arguments)}catch(U){$t("WebGLState:",U)}}function bt(){try{i.texStorage3D(...arguments)}catch(U){$t("WebGLState:",U)}}function at(){try{i.texImage2D(...arguments)}catch(U){$t("WebGLState:",U)}}function lt(){try{i.texImage3D(...arguments)}catch(U){$t("WebGLState:",U)}}function Tt(U){return p[U]!==void 0?p[U]:i.getParameter(U)}function J(U,ft){p[U]!==ft&&(i.pixelStorei(U,ft),p[U]=ft)}function nt(U){Dt.equals(U)===!1&&(i.scissor(U.x,U.y,U.z,U.w),Dt.copy(U))}function rt(U){Pt.equals(U)===!1&&(i.viewport(U.x,U.y,U.z,U.w),Pt.copy(U))}function pt(U,ft){let st=c.get(ft);st===void 0&&(st=new WeakMap,c.set(ft,st));let _t=st.get(U);_t===void 0&&(_t=i.getUniformBlockIndex(ft,U.name),st.set(U,_t))}function ct(U,ft){let _t=c.get(ft).get(U);l.get(ft)!==_t&&(i.uniformBlockBinding(ft,_t,U.__bindingPointIndex),l.set(ft,_t))}function vt(){i.disable(i.BLEND),i.disable(i.CULL_FACE),i.disable(i.DEPTH_TEST),i.disable(i.POLYGON_OFFSET_FILL),i.disable(i.SCISSOR_TEST),i.disable(i.STENCIL_TEST),i.disable(i.SAMPLE_ALPHA_TO_COVERAGE),i.blendEquation(i.FUNC_ADD),i.blendFunc(i.ONE,i.ZERO),i.blendFuncSeparate(i.ONE,i.ZERO,i.ONE,i.ZERO),i.blendColor(0,0,0,0),i.colorMask(!0,!0,!0,!0),i.clearColor(0,0,0,0),i.depthMask(!0),i.depthFunc(i.LESS),a.setReversed(!1),i.clearDepth(1),i.stencilMask(4294967295),i.stencilFunc(i.ALWAYS,0,4294967295),i.stencilOp(i.KEEP,i.KEEP,i.KEEP),i.clearStencil(0),i.cullFace(i.BACK),i.frontFace(i.CCW),i.polygonOffset(0,0),i.activeTexture(i.TEXTURE0),i.bindFramebuffer(i.FRAMEBUFFER,null),i.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),i.bindFramebuffer(i.READ_FRAMEBUFFER,null),i.useProgram(null),i.lineWidth(1),i.scissor(0,0,i.canvas.width,i.canvas.height),i.viewport(0,0,i.canvas.width,i.canvas.height),i.pixelStorei(i.PACK_ALIGNMENT,4),i.pixelStorei(i.UNPACK_ALIGNMENT,4),i.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,!1),i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1),i.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,i.BROWSER_DEFAULT_WEBGL),i.pixelStorei(i.PACK_ROW_LENGTH,0),i.pixelStorei(i.PACK_SKIP_PIXELS,0),i.pixelStorei(i.PACK_SKIP_ROWS,0),i.pixelStorei(i.UNPACK_ROW_LENGTH,0),i.pixelStorei(i.UNPACK_IMAGE_HEIGHT,0),i.pixelStorei(i.UNPACK_SKIP_PIXELS,0),i.pixelStorei(i.UNPACK_SKIP_ROWS,0),i.pixelStorei(i.UNPACK_SKIP_IMAGES,0),h={},p={},Y=null,tt={},d={},f=new WeakMap,_=[],b=null,m=!1,u=null,S=null,R=null,v=null,M=null,E=null,A=null,g=new jt(0,0,0),w=0,T=!1,I=null,N=null,B=null,F=null,P=null,Dt.set(0,0,i.canvas.width,i.canvas.height),Pt.set(0,0,i.canvas.width,i.canvas.height),r.reset(),a.reset(),o.reset()}return{buffers:{color:r,depth:a,stencil:o},enable:it,disable:gt,bindFramebuffer:zt,drawBuffers:Rt,useProgram:Yt,setBlending:ne,setMaterial:Kt,setFlipSided:te,setCullFace:xe,setLineWidth:ze,setPolygonOffset:Ne,setScissorTest:ge,activeTexture:Ee,bindTexture:W,unbindTexture:Pe,compressedTexImage2D:_e,compressedTexImage3D:C,texImage2D:at,texImage3D:lt,pixelStorei:J,getParameter:Tt,updateUBOMapping:pt,uniformBlockBinding:ct,texStorage2D:yt,texStorage3D:bt,texSubImage2D:x,texSubImage3D:K,compressedTexSubImage2D:j,compressedTexSubImage3D:ot,scissor:nt,viewport:rt,reset:vt}}function Jx(i,t,e,n,s,r,a){let o=t.has("WEBGL_multisampled_render_to_texture")?t.get("WEBGL_multisampled_render_to_texture"):null,l=typeof navigator>"u"?!1:/OculusBrowser/g.test(navigator.userAgent),c=new qt,h=new WeakMap,p=new Set,d,f=new WeakMap,_=!1;try{_=typeof OffscreenCanvas<"u"&&new OffscreenCanvas(1,1).getContext("2d")!==null}catch{}function b(C,x){return _?new OffscreenCanvas(C,x):ra("canvas")}function m(C,x,K){let j=1,ot=_e(C);if((ot.width>K||ot.height>K)&&(j=K/Math.max(ot.width,ot.height)),j<1)if(typeof HTMLImageElement<"u"&&C instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&C instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&C instanceof ImageBitmap||typeof VideoFrame<"u"&&C instanceof VideoFrame){let yt=Math.floor(j*ot.width),bt=Math.floor(j*ot.height);d===void 0&&(d=b(yt,bt));let at=x?b(yt,bt):d;return at.width=yt,at.height=bt,at.getContext("2d").drawImage(C,0,0,yt,bt),Zt("WebGLRenderer: Texture has been resized from ("+ot.width+"x"+ot.height+") to ("+yt+"x"+bt+")."),at}else return"data"in C&&Zt("WebGLRenderer: Image in DataTexture is too big ("+ot.width+"x"+ot.height+")."),C;return C}function u(C){return C.generateMipmaps}function S(C){i.generateMipmap(C)}function R(C){return C.isWebGLCubeRenderTarget?i.TEXTURE_CUBE_MAP:C.isWebGL3DRenderTarget?i.TEXTURE_3D:C.isWebGLArrayRenderTarget||C.isCompressedArrayTexture?i.TEXTURE_2D_ARRAY:i.TEXTURE_2D}function v(C,x,K,j,ot,yt=!1){if(C!==null){if(i[C]!==void 0)return i[C];Zt("WebGLRenderer: Attempt to use non-existing WebGL internal format '"+C+"'")}let bt;j&&(bt=t.get("EXT_texture_norm16"),bt||Zt("WebGLRenderer: Unable to use normalized textures without EXT_texture_norm16 extension"));let at=x;if(x===i.RED&&(K===i.FLOAT&&(at=i.R32F),K===i.HALF_FLOAT&&(at=i.R16F),K===i.UNSIGNED_BYTE&&(at=i.R8),K===i.UNSIGNED_SHORT&&bt&&(at=bt.R16_EXT),K===i.SHORT&&bt&&(at=bt.R16_SNORM_EXT)),x===i.RED_INTEGER&&(K===i.UNSIGNED_BYTE&&(at=i.R8UI),K===i.UNSIGNED_SHORT&&(at=i.R16UI),K===i.UNSIGNED_INT&&(at=i.R32UI),K===i.BYTE&&(at=i.R8I),K===i.SHORT&&(at=i.R16I),K===i.INT&&(at=i.R32I)),x===i.RG&&(K===i.FLOAT&&(at=i.RG32F),K===i.HALF_FLOAT&&(at=i.RG16F),K===i.UNSIGNED_BYTE&&(at=i.RG8),K===i.UNSIGNED_SHORT&&bt&&(at=bt.RG16_EXT),K===i.SHORT&&bt&&(at=bt.RG16_SNORM_EXT)),x===i.RG_INTEGER&&(K===i.UNSIGNED_BYTE&&(at=i.RG8UI),K===i.UNSIGNED_SHORT&&(at=i.RG16UI),K===i.UNSIGNED_INT&&(at=i.RG32UI),K===i.BYTE&&(at=i.RG8I),K===i.SHORT&&(at=i.RG16I),K===i.INT&&(at=i.RG32I)),x===i.RGB_INTEGER&&(K===i.UNSIGNED_BYTE&&(at=i.RGB8UI),K===i.UNSIGNED_SHORT&&(at=i.RGB16UI),K===i.UNSIGNED_INT&&(at=i.RGB32UI),K===i.BYTE&&(at=i.RGB8I),K===i.SHORT&&(at=i.RGB16I),K===i.INT&&(at=i.RGB32I)),x===i.RGBA_INTEGER&&(K===i.UNSIGNED_BYTE&&(at=i.RGBA8UI),K===i.UNSIGNED_SHORT&&(at=i.RGBA16UI),K===i.UNSIGNED_INT&&(at=i.RGBA32UI),K===i.BYTE&&(at=i.RGBA8I),K===i.SHORT&&(at=i.RGBA16I),K===i.INT&&(at=i.RGBA32I)),x===i.RGB&&(K===i.UNSIGNED_SHORT&&bt&&(at=bt.RGB16_EXT),K===i.SHORT&&bt&&(at=bt.RGB16_SNORM_EXT),K===i.UNSIGNED_INT_5_9_9_9_REV&&(at=i.RGB9_E5),K===i.UNSIGNED_INT_10F_11F_11F_REV&&(at=i.R11F_G11F_B10F)),x===i.RGBA){let lt=yt?sa:me.getTransfer(ot);K===i.FLOAT&&(at=i.RGBA32F),K===i.HALF_FLOAT&&(at=i.RGBA16F),K===i.UNSIGNED_BYTE&&(at=lt===we?i.SRGB8_ALPHA8:i.RGBA8),K===i.UNSIGNED_SHORT&&bt&&(at=bt.RGBA16_EXT),K===i.SHORT&&bt&&(at=bt.RGBA16_SNORM_EXT),K===i.UNSIGNED_SHORT_4_4_4_4&&(at=i.RGBA4),K===i.UNSIGNED_SHORT_5_5_5_1&&(at=i.RGB5_A1)}return(at===i.R16F||at===i.R32F||at===i.RG16F||at===i.RG32F||at===i.RGBA16F||at===i.RGBA32F)&&t.get("EXT_color_buffer_float"),at}function M(C,x){let K;return C?x===null||x===ri||x===Rr?K=i.DEPTH24_STENCIL8:x===Vn?K=i.DEPTH32F_STENCIL8:x===Ar&&(K=i.DEPTH24_STENCIL8,Zt("DepthTexture: 16 bit depth attachment is not supported with stencil. Using 24-bit attachment.")):x===null||x===ri||x===Rr?K=i.DEPTH_COMPONENT24:x===Vn?K=i.DEPTH_COMPONENT32F:x===Ar&&(K=i.DEPTH_COMPONENT16),K}function E(C,x){return u(C)===!0||C.isFramebufferTexture&&C.minFilter!==tn&&C.minFilter!==ln?Math.log2(Math.max(x.width,x.height))+1:C.mipmaps!==void 0&&C.mipmaps.length>0?C.mipmaps.length:C.isCompressedTexture&&Array.isArray(C.image)?x.mipmaps.length:1}function A(C){let x=C.target;x.removeEventListener("dispose",A),w(x),x.isVideoTexture&&h.delete(x),x.isHTMLTexture&&p.delete(x)}function g(C){let x=C.target;x.removeEventListener("dispose",g),I(x)}function w(C){let x=n.get(C);if(x.__webglInit===void 0)return;let K=C.source,j=f.get(K);if(j){let ot=j[x.__cacheKey];ot.usedTimes--,ot.usedTimes===0&&T(C),Object.keys(j).length===0&&f.delete(K)}n.remove(C)}function T(C){let x=n.get(C);i.deleteTexture(x.__webglTexture);let K=C.source,j=f.get(K);delete j[x.__cacheKey],a.memory.textures--}function I(C){let x=n.get(C);if(C.depthTexture&&(C.depthTexture.dispose(),n.remove(C.depthTexture)),C.isWebGLCubeRenderTarget)for(let j=0;j<6;j++){if(Array.isArray(x.__webglFramebuffer[j]))for(let ot=0;ot<x.__webglFramebuffer[j].length;ot++)i.deleteFramebuffer(x.__webglFramebuffer[j][ot]);else i.deleteFramebuffer(x.__webglFramebuffer[j]);x.__webglDepthbuffer&&i.deleteRenderbuffer(x.__webglDepthbuffer[j])}else{if(Array.isArray(x.__webglFramebuffer))for(let j=0;j<x.__webglFramebuffer.length;j++)i.deleteFramebuffer(x.__webglFramebuffer[j]);else i.deleteFramebuffer(x.__webglFramebuffer);if(x.__webglDepthbuffer&&i.deleteRenderbuffer(x.__webglDepthbuffer),x.__webglMultisampledFramebuffer&&i.deleteFramebuffer(x.__webglMultisampledFramebuffer),x.__webglColorRenderbuffer)for(let j=0;j<x.__webglColorRenderbuffer.length;j++)x.__webglColorRenderbuffer[j]&&i.deleteRenderbuffer(x.__webglColorRenderbuffer[j]);x.__webglDepthRenderbuffer&&i.deleteRenderbuffer(x.__webglDepthRenderbuffer)}let K=C.textures;for(let j=0,ot=K.length;j<ot;j++){let yt=n.get(K[j]);yt.__webglTexture&&(i.deleteTexture(yt.__webglTexture),a.memory.textures--),n.remove(K[j])}n.remove(C)}let N=0;function B(){N=0}function F(){return N}function P(C){N=C}function V(){let C=N;return C>=s.maxTextures&&Zt("WebGLTextures: Trying to use "+(C+1)+" texture units while this GPU supports only "+s.maxTextures),N+=1,C}function z(C){let x=[];return x.push(C.wrapS),x.push(C.wrapT),x.push(C.wrapR||0),x.push(C.magFilter),x.push(C.minFilter),x.push(C.anisotropy),x.push(C.internalFormat),x.push(C.format),x.push(C.type),x.push(C.generateMipmaps),x.push(C.premultiplyAlpha),x.push(C.flipY),x.push(C.unpackAlignment),x.push(C.colorSpace),x.join()}function X(C,x){let K=n.get(C);if(C.isVideoTexture&&W(C),C.isRenderTargetTexture===!1&&C.isExternalTexture!==!0&&C.version>0&&K.__version!==C.version){let j=C.image;if(j===null)Zt("WebGLRenderer: Texture marked for update but no image data found.");else if(j.complete===!1)Zt("WebGLRenderer: Texture marked for update but image is incomplete");else{gt(K,C,x);return}}else C.isExternalTexture&&(K.__webglTexture=C.sourceTexture?C.sourceTexture:null);e.bindTexture(i.TEXTURE_2D,K.__webglTexture,i.TEXTURE0+x)}function G(C,x){let K=n.get(C);if(C.isRenderTargetTexture===!1&&C.version>0&&K.__version!==C.version){gt(K,C,x);return}else C.isExternalTexture&&(K.__webglTexture=C.sourceTexture?C.sourceTexture:null);e.bindTexture(i.TEXTURE_2D_ARRAY,K.__webglTexture,i.TEXTURE0+x)}function Y(C,x){let K=n.get(C);if(C.isRenderTargetTexture===!1&&C.version>0&&K.__version!==C.version){gt(K,C,x);return}e.bindTexture(i.TEXTURE_3D,K.__webglTexture,i.TEXTURE0+x)}function tt(C,x){let K=n.get(C);if(C.isCubeDepthTexture!==!0&&C.version>0&&K.__version!==C.version){zt(K,C,x);return}e.bindTexture(i.TEXTURE_CUBE_MAP,K.__webglTexture,i.TEXTURE0+x)}let et={[gi]:i.REPEAT,[mi]:i.CLAMP_TO_EDGE,[go]:i.MIRRORED_REPEAT},dt={[tn]:i.NEAREST,[Nu]:i.NEAREST_MIPMAP_NEAREST,[ba]:i.NEAREST_MIPMAP_LINEAR,[ln]:i.LINEAR,[Ho]:i.LINEAR_MIPMAP_NEAREST,[gs]:i.LINEAR_MIPMAP_LINEAR},Dt={[Bu]:i.NEVER,[Wu]:i.ALWAYS,[ku]:i.LESS,[Tl]:i.LEQUAL,[Hu]:i.EQUAL,[Al]:i.GEQUAL,[Vu]:i.GREATER,[Gu]:i.NOTEQUAL};function Pt(C,x){if(x.type===Vn&&t.has("OES_texture_float_linear")===!1&&(x.magFilter===ln||x.magFilter===Ho||x.magFilter===ba||x.magFilter===gs||x.minFilter===ln||x.minFilter===Ho||x.minFilter===ba||x.minFilter===gs)&&Zt("WebGLRenderer: Unable to use linear filtering with floating point textures. OES_texture_float_linear not supported on this device."),i.texParameteri(C,i.TEXTURE_WRAP_S,et[x.wrapS]),i.texParameteri(C,i.TEXTURE_WRAP_T,et[x.wrapT]),(C===i.TEXTURE_3D||C===i.TEXTURE_2D_ARRAY)&&i.texParameteri(C,i.TEXTURE_WRAP_R,et[x.wrapR]),i.texParameteri(C,i.TEXTURE_MAG_FILTER,dt[x.magFilter]),i.texParameteri(C,i.TEXTURE_MIN_FILTER,dt[x.minFilter]),x.compareFunction&&(i.texParameteri(C,i.TEXTURE_COMPARE_MODE,i.COMPARE_REF_TO_TEXTURE),i.texParameteri(C,i.TEXTURE_COMPARE_FUNC,Dt[x.compareFunction])),t.has("EXT_texture_filter_anisotropic")===!0){if(x.magFilter===tn||x.minFilter!==ba&&x.minFilter!==gs||x.type===Vn&&t.has("OES_texture_float_linear")===!1)return;if(x.anisotropy>1||n.get(x).__currentAnisotropy){let K=t.get("EXT_texture_filter_anisotropic");i.texParameterf(C,K.TEXTURE_MAX_ANISOTROPY_EXT,Math.min(x.anisotropy,s.getMaxAnisotropy())),n.get(x).__currentAnisotropy=x.anisotropy}}}function xt(C,x){let K=!1;C.__webglInit===void 0&&(C.__webglInit=!0,x.addEventListener("dispose",A));let j=x.source,ot=f.get(j);ot===void 0&&(ot={},f.set(j,ot));let yt=z(x);if(yt!==C.__cacheKey){ot[yt]===void 0&&(ot[yt]={texture:i.createTexture(),usedTimes:0},a.memory.textures++,K=!0),ot[yt].usedTimes++;let bt=ot[C.__cacheKey];bt!==void 0&&(ot[C.__cacheKey].usedTimes--,bt.usedTimes===0&&T(x)),C.__cacheKey=yt,C.__webglTexture=ot[yt].texture}return K}function q(C,x,K){return Math.floor(Math.floor(C/K)/x)}function it(C,x,K,j){let yt=C.updateRanges;if(yt.length===0)e.texSubImage2D(i.TEXTURE_2D,0,0,0,x.width,x.height,K,j,x.data);else{yt.sort((J,nt)=>J.start-nt.start);let bt=0;for(let J=1;J<yt.length;J++){let nt=yt[bt],rt=yt[J],pt=nt.start+nt.count,ct=q(rt.start,x.width,4),vt=q(nt.start,x.width,4);rt.start<=pt+1&&ct===vt&&q(rt.start+rt.count-1,x.width,4)===ct?nt.count=Math.max(nt.count,rt.start+rt.count-nt.start):(++bt,yt[bt]=rt)}yt.length=bt+1;let at=e.getParameter(i.UNPACK_ROW_LENGTH),lt=e.getParameter(i.UNPACK_SKIP_PIXELS),Tt=e.getParameter(i.UNPACK_SKIP_ROWS);e.pixelStorei(i.UNPACK_ROW_LENGTH,x.width);for(let J=0,nt=yt.length;J<nt;J++){let rt=yt[J],pt=Math.floor(rt.start/4),ct=Math.ceil(rt.count/4),vt=pt%x.width,U=Math.floor(pt/x.width),ft=ct,st=1;e.pixelStorei(i.UNPACK_SKIP_PIXELS,vt),e.pixelStorei(i.UNPACK_SKIP_ROWS,U),e.texSubImage2D(i.TEXTURE_2D,0,vt,U,ft,st,K,j,x.data)}C.clearUpdateRanges(),e.pixelStorei(i.UNPACK_ROW_LENGTH,at),e.pixelStorei(i.UNPACK_SKIP_PIXELS,lt),e.pixelStorei(i.UNPACK_SKIP_ROWS,Tt)}}function gt(C,x,K){let j=i.TEXTURE_2D;(x.isDataArrayTexture||x.isCompressedArrayTexture)&&(j=i.TEXTURE_2D_ARRAY),x.isData3DTexture&&(j=i.TEXTURE_3D);let ot=xt(C,x),yt=x.source;e.bindTexture(j,C.__webglTexture,i.TEXTURE0+K);let bt=n.get(yt);if(yt.version!==bt.__version||ot===!0){if(e.activeTexture(i.TEXTURE0+K),(typeof ImageBitmap<"u"&&x.image instanceof ImageBitmap)===!1){let st=me.getPrimaries(me.workingColorSpace),_t=x.colorSpace===Wi?null:me.getPrimaries(x.colorSpace),Mt=x.colorSpace===Wi||st===_t?i.NONE:i.BROWSER_DEFAULT_WEBGL;e.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,x.flipY),e.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,x.premultiplyAlpha),e.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,Mt)}e.pixelStorei(i.UNPACK_ALIGNMENT,x.unpackAlignment);let lt=m(x.image,!1,s.maxTextureSize);lt=Pe(x,lt);let Tt=r.convert(x.format,x.colorSpace),J=r.convert(x.type),nt=v(x.internalFormat,Tt,J,x.normalized,x.colorSpace,x.isVideoTexture);Pt(j,x);let rt,pt=x.mipmaps,ct=x.isVideoTexture!==!0,vt=bt.__version===void 0||ot===!0,U=yt.dataReady,ft=E(x,lt);if(x.isDepthTexture)nt=M(x.format===xs,x.type),vt&&(ct?e.texStorage2D(i.TEXTURE_2D,1,nt,lt.width,lt.height):e.texImage2D(i.TEXTURE_2D,0,nt,lt.width,lt.height,0,Tt,J,null));else if(x.isDataTexture)if(pt.length>0){ct&&vt&&e.texStorage2D(i.TEXTURE_2D,ft,nt,pt[0].width,pt[0].height);for(let st=0,_t=pt.length;st<_t;st++)rt=pt[st],ct?U&&e.texSubImage2D(i.TEXTURE_2D,st,0,0,rt.width,rt.height,Tt,J,rt.data):e.texImage2D(i.TEXTURE_2D,st,nt,rt.width,rt.height,0,Tt,J,rt.data);x.generateMipmaps=!1}else ct?(vt&&e.texStorage2D(i.TEXTURE_2D,ft,nt,lt.width,lt.height),U&&it(x,lt,Tt,J)):e.texImage2D(i.TEXTURE_2D,0,nt,lt.width,lt.height,0,Tt,J,lt.data);else if(x.isCompressedTexture)if(x.isCompressedArrayTexture){ct&&vt&&e.texStorage3D(i.TEXTURE_2D_ARRAY,ft,nt,pt[0].width,pt[0].height,lt.depth);for(let st=0,_t=pt.length;st<_t;st++)if(rt=pt[st],x.format!==Gn)if(Tt!==null)if(ct){if(U)if(x.layerUpdates.size>0){let Mt=Qc(rt.width,rt.height,x.format,x.type);for(let ut of x.layerUpdates){let Gt=rt.data.subarray(ut*Mt/rt.data.BYTES_PER_ELEMENT,(ut+1)*Mt/rt.data.BYTES_PER_ELEMENT);e.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,st,0,0,ut,rt.width,rt.height,1,Tt,Gt)}}else e.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,st,0,0,0,rt.width,rt.height,lt.depth,Tt,rt.data)}else e.compressedTexImage3D(i.TEXTURE_2D_ARRAY,st,nt,rt.width,rt.height,lt.depth,0,rt.data,0,0);else Zt("WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()");else ct?U&&e.texSubImage3D(i.TEXTURE_2D_ARRAY,st,0,0,0,rt.width,rt.height,lt.depth,Tt,J,rt.data):e.texImage3D(i.TEXTURE_2D_ARRAY,st,nt,rt.width,rt.height,lt.depth,0,Tt,J,rt.data);x.layerUpdates.size>0&&x.clearLayerUpdates()}else{ct&&vt&&e.texStorage2D(i.TEXTURE_2D,ft,nt,pt[0].width,pt[0].height);for(let st=0,_t=pt.length;st<_t;st++)rt=pt[st],x.format!==Gn?Tt!==null?ct?U&&e.compressedTexSubImage2D(i.TEXTURE_2D,st,0,0,rt.width,rt.height,Tt,rt.data):e.compressedTexImage2D(i.TEXTURE_2D,st,nt,rt.width,rt.height,0,rt.data):Zt("WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()"):ct?U&&e.texSubImage2D(i.TEXTURE_2D,st,0,0,rt.width,rt.height,Tt,J,rt.data):e.texImage2D(i.TEXTURE_2D,st,nt,rt.width,rt.height,0,Tt,J,rt.data)}else if(x.isDataArrayTexture)if(ct){if(vt&&e.texStorage3D(i.TEXTURE_2D_ARRAY,ft,nt,lt.width,lt.height,lt.depth),U)if(x.layerUpdates.size>0){let st=Qc(lt.width,lt.height,x.format,x.type);for(let _t of x.layerUpdates){let Mt=lt.data.subarray(_t*st/lt.data.BYTES_PER_ELEMENT,(_t+1)*st/lt.data.BYTES_PER_ELEMENT);e.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,_t,lt.width,lt.height,1,Tt,J,Mt)}x.clearLayerUpdates()}else e.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,0,lt.width,lt.height,lt.depth,Tt,J,lt.data)}else e.texImage3D(i.TEXTURE_2D_ARRAY,0,nt,lt.width,lt.height,lt.depth,0,Tt,J,lt.data);else if(x.isData3DTexture)ct?(vt&&e.texStorage3D(i.TEXTURE_3D,ft,nt,lt.width,lt.height,lt.depth),U&&e.texSubImage3D(i.TEXTURE_3D,0,0,0,0,lt.width,lt.height,lt.depth,Tt,J,lt.data)):e.texImage3D(i.TEXTURE_3D,0,nt,lt.width,lt.height,lt.depth,0,Tt,J,lt.data);else if(x.isFramebufferTexture){if(vt)if(ct)e.texStorage2D(i.TEXTURE_2D,ft,nt,lt.width,lt.height);else{let st=lt.width,_t=lt.height;for(let Mt=0;Mt<ft;Mt++)e.texImage2D(i.TEXTURE_2D,Mt,nt,st,_t,0,Tt,J,null),st>>=1,_t>>=1}}else if(x.isHTMLTexture){if("texElementImage2D"in i){let st=i.canvas;if(st.hasAttribute("layoutsubtree")||st.setAttribute("layoutsubtree","true"),lt.parentNode!==st){st.appendChild(lt),p.add(x),st.onpaint=_t=>{let Mt=_t.changedElements;for(let ut of p)Mt.includes(ut.image)&&(ut.needsUpdate=!0)},st.requestPaint();return}if(i.texElementImage2D.length===3)i.texElementImage2D(i.TEXTURE_2D,i.RGBA8,lt);else{let Mt=i.RGBA,ut=i.RGBA,Gt=i.UNSIGNED_BYTE;i.texElementImage2D(i.TEXTURE_2D,0,Mt,ut,Gt,lt)}i.texParameteri(i.TEXTURE_2D,i.TEXTURE_MIN_FILTER,i.LINEAR),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_S,i.CLAMP_TO_EDGE),i.texParameteri(i.TEXTURE_2D,i.TEXTURE_WRAP_T,i.CLAMP_TO_EDGE)}}else if(pt.length>0){if(ct&&vt){let st=_e(pt[0]);e.texStorage2D(i.TEXTURE_2D,ft,nt,st.width,st.height)}for(let st=0,_t=pt.length;st<_t;st++)rt=pt[st],ct?U&&e.texSubImage2D(i.TEXTURE_2D,st,0,0,Tt,J,rt):e.texImage2D(i.TEXTURE_2D,st,nt,Tt,J,rt);x.generateMipmaps=!1}else if(ct){if(vt){let st=_e(lt);e.texStorage2D(i.TEXTURE_2D,ft,nt,st.width,st.height)}U&&e.texSubImage2D(i.TEXTURE_2D,0,0,0,Tt,J,lt)}else e.texImage2D(i.TEXTURE_2D,0,nt,Tt,J,lt);u(x)&&S(j),bt.__version=yt.version,x.onUpdate&&x.onUpdate(x)}C.__version=x.version}function zt(C,x,K){if(x.image.length!==6)return;let j=xt(C,x),ot=x.source;e.bindTexture(i.TEXTURE_CUBE_MAP,C.__webglTexture,i.TEXTURE0+K);let yt=n.get(ot);if(ot.version!==yt.__version||j===!0){e.activeTexture(i.TEXTURE0+K);let bt=me.getPrimaries(me.workingColorSpace),at=x.colorSpace===Wi?null:me.getPrimaries(x.colorSpace),lt=x.colorSpace===Wi||bt===at?i.NONE:i.BROWSER_DEFAULT_WEBGL;e.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,x.flipY),e.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,x.premultiplyAlpha),e.pixelStorei(i.UNPACK_ALIGNMENT,x.unpackAlignment),e.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,lt);let Tt=x.isCompressedTexture||x.image[0].isCompressedTexture,J=x.image[0]&&x.image[0].isDataTexture,nt=[];for(let ut=0;ut<6;ut++)!Tt&&!J?nt[ut]=m(x.image[ut],!0,s.maxCubemapSize):nt[ut]=J?x.image[ut].image:x.image[ut],nt[ut]=Pe(x,nt[ut]);let rt=nt[0],pt=r.convert(x.format,x.colorSpace),ct=r.convert(x.type),vt=v(x.internalFormat,pt,ct,x.normalized,x.colorSpace),U=x.isVideoTexture!==!0,ft=yt.__version===void 0||j===!0,st=ot.dataReady,_t=E(x,rt);Pt(i.TEXTURE_CUBE_MAP,x);let Mt;if(Tt){U&&ft&&e.texStorage2D(i.TEXTURE_CUBE_MAP,_t,vt,rt.width,rt.height);for(let ut=0;ut<6;ut++){Mt=nt[ut].mipmaps;for(let Gt=0;Gt<Mt.length;Gt++){let kt=Mt[Gt];x.format!==Gn?pt!==null?U?st&&e.compressedTexSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,Gt,0,0,kt.width,kt.height,pt,kt.data):e.compressedTexImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,Gt,vt,kt.width,kt.height,0,kt.data):Zt("WebGLRenderer: Attempt to load unsupported compressed texture format in .setTextureCube()"):U?st&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,Gt,0,0,kt.width,kt.height,pt,ct,kt.data):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,Gt,vt,kt.width,kt.height,0,pt,ct,kt.data)}}}else{if(Mt=x.mipmaps,U&&ft){Mt.length>0&&_t++;let ut=_e(nt[0]);e.texStorage2D(i.TEXTURE_CUBE_MAP,_t,vt,ut.width,ut.height)}for(let ut=0;ut<6;ut++)if(J){U?st&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,0,0,0,nt[ut].width,nt[ut].height,pt,ct,nt[ut].data):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,0,vt,nt[ut].width,nt[ut].height,0,pt,ct,nt[ut].data);for(let Gt=0;Gt<Mt.length;Gt++){let fe=Mt[Gt].image[ut].image;U?st&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,Gt+1,0,0,fe.width,fe.height,pt,ct,fe.data):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,Gt+1,vt,fe.width,fe.height,0,pt,ct,fe.data)}}else{U?st&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,0,0,0,pt,ct,nt[ut]):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,0,vt,pt,ct,nt[ut]);for(let Gt=0;Gt<Mt.length;Gt++){let kt=Mt[Gt];U?st&&e.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,Gt+1,0,0,pt,ct,kt.image[ut]):e.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+ut,Gt+1,vt,pt,ct,kt.image[ut])}}}u(x)&&S(i.TEXTURE_CUBE_MAP),yt.__version=ot.version,x.onUpdate&&x.onUpdate(x)}C.__version=x.version}function Rt(C,x,K,j,ot,yt){let bt=r.convert(K.format,K.colorSpace),at=r.convert(K.type),lt=v(K.internalFormat,bt,at,K.normalized,K.colorSpace),Tt=n.get(x),J=n.get(K);if(J.__renderTarget=x,!Tt.__hasExternalTextures){let nt=Math.max(1,x.width>>yt),rt=Math.max(1,x.height>>yt);ot===i.TEXTURE_3D||ot===i.TEXTURE_2D_ARRAY?e.texImage3D(ot,yt,lt,nt,rt,x.depth,0,bt,at,null):e.texImage2D(ot,yt,lt,nt,rt,0,bt,at,null)}e.bindFramebuffer(i.FRAMEBUFFER,C),Ee(x)?o.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,j,ot,J.__webglTexture,0,ge(x)):(ot===i.TEXTURE_2D||ot>=i.TEXTURE_CUBE_MAP_POSITIVE_X&&ot<=i.TEXTURE_CUBE_MAP_NEGATIVE_Z)&&i.framebufferTexture2D(i.FRAMEBUFFER,j,ot,J.__webglTexture,yt),e.bindFramebuffer(i.FRAMEBUFFER,null)}function Yt(C,x,K){if(i.bindRenderbuffer(i.RENDERBUFFER,C),x.depthBuffer){let j=x.depthTexture,ot=j&&j.isDepthTexture?j.type:null,yt=M(x.stencilBuffer,ot),bt=x.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT;Ee(x)?o.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,ge(x),yt,x.width,x.height):K?i.renderbufferStorageMultisample(i.RENDERBUFFER,ge(x),yt,x.width,x.height):i.renderbufferStorage(i.RENDERBUFFER,yt,x.width,x.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,bt,i.RENDERBUFFER,C)}else{let j=x.textures;for(let ot=0;ot<j.length;ot++){let yt=j[ot],bt=r.convert(yt.format,yt.colorSpace),at=r.convert(yt.type),lt=v(yt.internalFormat,bt,at,yt.normalized,yt.colorSpace);Ee(x)?o.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,ge(x),lt,x.width,x.height):K?i.renderbufferStorageMultisample(i.RENDERBUFFER,ge(x),lt,x.width,x.height):i.renderbufferStorage(i.RENDERBUFFER,lt,x.width,x.height)}}i.bindRenderbuffer(i.RENDERBUFFER,null)}function Me(C,x,K){let j=x.isWebGLCubeRenderTarget===!0;if(e.bindFramebuffer(i.FRAMEBUFFER,C),!(x.depthTexture&&x.depthTexture.isDepthTexture))throw new Error("THREE.WebGLTextures: renderTarget.depthTexture must be an instance of THREE.DepthTexture.");let ot=n.get(x.depthTexture);if(ot.__renderTarget=x,(!ot.__webglTexture||x.depthTexture.image.width!==x.width||x.depthTexture.image.height!==x.height)&&(x.depthTexture.image.width=x.width,x.depthTexture.image.height=x.height,x.depthTexture.needsUpdate=!0),j){if(ot.__webglInit===void 0&&(ot.__webglInit=!0,x.depthTexture.addEventListener("dispose",A)),ot.__webglTexture===void 0){ot.__webglTexture=i.createTexture(),e.bindTexture(i.TEXTURE_CUBE_MAP,ot.__webglTexture),Pt(i.TEXTURE_CUBE_MAP,x.depthTexture);let Tt=r.convert(x.depthTexture.format),J=r.convert(x.depthTexture.type),nt;x.depthTexture.format===xi?nt=i.DEPTH_COMPONENT24:x.depthTexture.format===xs&&(nt=i.DEPTH24_STENCIL8);for(let rt=0;rt<6;rt++)i.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+rt,0,nt,x.width,x.height,0,Tt,J,null)}}else X(x.depthTexture,0);let yt=ot.__webglTexture,bt=ge(x),at=j?i.TEXTURE_CUBE_MAP_POSITIVE_X+K:i.TEXTURE_2D,lt=x.depthTexture.format===xs?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT;if(x.depthTexture.format===xi)Ee(x)?o.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,lt,at,yt,0,bt):i.framebufferTexture2D(i.FRAMEBUFFER,lt,at,yt,0);else if(x.depthTexture.format===xs)Ee(x)?o.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,lt,at,yt,0,bt):i.framebufferTexture2D(i.FRAMEBUFFER,lt,at,yt,0);else throw new Error("THREE.WebGLTextures: Unknown depthTexture format.")}function Qt(C){let x=n.get(C),K=C.isWebGLCubeRenderTarget===!0;if(x.__boundDepthTexture!==C.depthTexture){let j=C.depthTexture;if(x.__depthDisposeCallback&&x.__depthDisposeCallback(),j){let ot=()=>{delete x.__boundDepthTexture,delete x.__depthDisposeCallback,j.removeEventListener("dispose",ot)};j.addEventListener("dispose",ot),x.__depthDisposeCallback=ot}x.__boundDepthTexture=j}if(C.depthTexture&&!x.__autoAllocateDepthBuffer)if(K)for(let j=0;j<6;j++)Me(x.__webglFramebuffer[j],C,j);else{let j=C.texture.mipmaps;j&&j.length>0?Me(x.__webglFramebuffer[0],C,0):Me(x.__webglFramebuffer,C,0)}else if(K){x.__webglDepthbuffer=[];for(let j=0;j<6;j++)if(e.bindFramebuffer(i.FRAMEBUFFER,x.__webglFramebuffer[j]),x.__webglDepthbuffer[j]===void 0)x.__webglDepthbuffer[j]=i.createRenderbuffer(),Yt(x.__webglDepthbuffer[j],C,!1);else{let ot=C.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,yt=x.__webglDepthbuffer[j];i.bindRenderbuffer(i.RENDERBUFFER,yt),i.framebufferRenderbuffer(i.FRAMEBUFFER,ot,i.RENDERBUFFER,yt)}}else{let j=C.texture.mipmaps;if(j&&j.length>0?e.bindFramebuffer(i.FRAMEBUFFER,x.__webglFramebuffer[0]):e.bindFramebuffer(i.FRAMEBUFFER,x.__webglFramebuffer),x.__webglDepthbuffer===void 0)x.__webglDepthbuffer=i.createRenderbuffer(),Yt(x.__webglDepthbuffer,C,!1);else{let ot=C.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,yt=x.__webglDepthbuffer;i.bindRenderbuffer(i.RENDERBUFFER,yt),i.framebufferRenderbuffer(i.FRAMEBUFFER,ot,i.RENDERBUFFER,yt)}}e.bindFramebuffer(i.FRAMEBUFFER,null)}function ne(C,x,K){let j=n.get(C);x!==void 0&&Rt(j.__webglFramebuffer,C,C.texture,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,0),K!==void 0&&Qt(C)}function Kt(C){let x=C.texture,K=n.get(C),j=n.get(x);C.addEventListener("dispose",g);let ot=C.textures,yt=C.isWebGLCubeRenderTarget===!0,bt=ot.length>1;if(bt||(j.__webglTexture===void 0&&(j.__webglTexture=i.createTexture()),j.__version=x.version,a.memory.textures++),yt){K.__webglFramebuffer=[];for(let at=0;at<6;at++)if(x.mipmaps&&x.mipmaps.length>0){K.__webglFramebuffer[at]=[];for(let lt=0;lt<x.mipmaps.length;lt++)K.__webglFramebuffer[at][lt]=i.createFramebuffer()}else K.__webglFramebuffer[at]=i.createFramebuffer()}else{if(x.mipmaps&&x.mipmaps.length>0){K.__webglFramebuffer=[];for(let at=0;at<x.mipmaps.length;at++)K.__webglFramebuffer[at]=i.createFramebuffer()}else K.__webglFramebuffer=i.createFramebuffer();if(bt)for(let at=0,lt=ot.length;at<lt;at++){let Tt=n.get(ot[at]);Tt.__webglTexture===void 0&&(Tt.__webglTexture=i.createTexture(),a.memory.textures++)}if(C.samples>0&&Ee(C)===!1){K.__webglMultisampledFramebuffer=i.createFramebuffer(),K.__webglColorRenderbuffer=[],e.bindFramebuffer(i.FRAMEBUFFER,K.__webglMultisampledFramebuffer);for(let at=0;at<ot.length;at++){let lt=ot[at];K.__webglColorRenderbuffer[at]=i.createRenderbuffer(),i.bindRenderbuffer(i.RENDERBUFFER,K.__webglColorRenderbuffer[at]);let Tt=r.convert(lt.format,lt.colorSpace),J=r.convert(lt.type),nt=v(lt.internalFormat,Tt,J,lt.normalized,lt.colorSpace,C.isXRRenderTarget===!0),rt=ge(C);i.renderbufferStorageMultisample(i.RENDERBUFFER,rt,nt,C.width,C.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+at,i.RENDERBUFFER,K.__webglColorRenderbuffer[at])}i.bindRenderbuffer(i.RENDERBUFFER,null),C.depthBuffer&&(K.__webglDepthRenderbuffer=i.createRenderbuffer(),Yt(K.__webglDepthRenderbuffer,C,!0)),e.bindFramebuffer(i.FRAMEBUFFER,null)}}if(yt){e.bindTexture(i.TEXTURE_CUBE_MAP,j.__webglTexture),Pt(i.TEXTURE_CUBE_MAP,x);for(let at=0;at<6;at++)if(x.mipmaps&&x.mipmaps.length>0)for(let lt=0;lt<x.mipmaps.length;lt++)Rt(K.__webglFramebuffer[at][lt],C,x,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+at,lt);else Rt(K.__webglFramebuffer[at],C,x,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+at,0);u(x)&&S(i.TEXTURE_CUBE_MAP),e.unbindTexture()}else if(bt){for(let at=0,lt=ot.length;at<lt;at++){let Tt=ot[at],J=n.get(Tt),nt=i.TEXTURE_2D;(C.isWebGL3DRenderTarget||C.isWebGLArrayRenderTarget)&&(nt=C.isWebGL3DRenderTarget?i.TEXTURE_3D:i.TEXTURE_2D_ARRAY),e.bindTexture(nt,J.__webglTexture),Pt(nt,Tt),Rt(K.__webglFramebuffer,C,Tt,i.COLOR_ATTACHMENT0+at,nt,0),u(Tt)&&S(nt)}e.unbindTexture()}else{let at=i.TEXTURE_2D;if((C.isWebGL3DRenderTarget||C.isWebGLArrayRenderTarget)&&(at=C.isWebGL3DRenderTarget?i.TEXTURE_3D:i.TEXTURE_2D_ARRAY),e.bindTexture(at,j.__webglTexture),Pt(at,x),x.mipmaps&&x.mipmaps.length>0)for(let lt=0;lt<x.mipmaps.length;lt++)Rt(K.__webglFramebuffer[lt],C,x,i.COLOR_ATTACHMENT0,at,lt);else Rt(K.__webglFramebuffer,C,x,i.COLOR_ATTACHMENT0,at,0);u(x)&&S(at),e.unbindTexture()}C.depthBuffer&&Qt(C)}function te(C){let x=C.textures;for(let K=0,j=x.length;K<j;K++){let ot=x[K];if(u(ot)){let yt=R(C),bt=n.get(ot).__webglTexture;e.bindTexture(yt,bt),S(yt),e.unbindTexture()}}}let xe=[],ze=[];function Ne(C){if(C.samples>0){if(Ee(C)===!1){let x=C.textures,K=C.width,j=C.height,ot=i.COLOR_BUFFER_BIT,yt=C.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,bt=n.get(C),at=x.length>1;if(at)for(let Tt=0;Tt<x.length;Tt++)e.bindFramebuffer(i.FRAMEBUFFER,bt.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+Tt,i.RENDERBUFFER,null),e.bindFramebuffer(i.FRAMEBUFFER,bt.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+Tt,i.TEXTURE_2D,null,0);e.bindFramebuffer(i.READ_FRAMEBUFFER,bt.__webglMultisampledFramebuffer);let lt=C.texture.mipmaps;lt&&lt.length>0?e.bindFramebuffer(i.DRAW_FRAMEBUFFER,bt.__webglFramebuffer[0]):e.bindFramebuffer(i.DRAW_FRAMEBUFFER,bt.__webglFramebuffer);for(let Tt=0;Tt<x.length;Tt++){if(C.resolveDepthBuffer&&(C.depthBuffer&&(ot|=i.DEPTH_BUFFER_BIT),C.stencilBuffer&&C.resolveStencilBuffer&&(ot|=i.STENCIL_BUFFER_BIT)),at){i.framebufferRenderbuffer(i.READ_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.RENDERBUFFER,bt.__webglColorRenderbuffer[Tt]);let J=n.get(x[Tt]).__webglTexture;i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,J,0)}i.blitFramebuffer(0,0,K,j,0,0,K,j,ot,i.NEAREST),l===!0&&(xe.length=0,ze.length=0,xe.push(i.COLOR_ATTACHMENT0+Tt),C.depthBuffer&&C.storeMultisampledDepthBuffer===!1&&(xe.push(yt),ze.push(yt),i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,ze)),i.invalidateFramebuffer(i.READ_FRAMEBUFFER,xe))}if(e.bindFramebuffer(i.READ_FRAMEBUFFER,null),e.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),at)for(let Tt=0;Tt<x.length;Tt++){e.bindFramebuffer(i.FRAMEBUFFER,bt.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+Tt,i.RENDERBUFFER,bt.__webglColorRenderbuffer[Tt]);let J=n.get(x[Tt]).__webglTexture;e.bindFramebuffer(i.FRAMEBUFFER,bt.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+Tt,i.TEXTURE_2D,J,0)}e.bindFramebuffer(i.DRAW_FRAMEBUFFER,bt.__webglMultisampledFramebuffer)}else if(C.depthBuffer&&C.storeMultisampledDepthBuffer===!1&&l){let x=C.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT;i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,[x])}}}function ge(C){return Math.min(s.maxSamples,C.samples)}function Ee(C){let x=n.get(C);return C.samples>0&&t.has("WEBGL_multisampled_render_to_texture")===!0&&x.__useRenderToTexture!==!1}function W(C){let x=a.render.frame;h.get(C)!==x&&(h.set(C,x),C.update())}function Pe(C,x){let K=C.colorSpace,j=C.format,ot=C.type;return C.isCompressedTexture===!0||C.isVideoTexture===!0||K!==ia&&K!==Wi&&(me.getTransfer(K)===we?(j!==Gn||ot!==An)&&Zt("WebGLTextures: sRGB encoded textures have to use RGBAFormat and UnsignedByteType."):$t("WebGLTextures: Unsupported texture color space:",K)),x}function _e(C){return typeof HTMLImageElement<"u"&&C instanceof HTMLImageElement?(c.width=C.naturalWidth||C.width,c.height=C.naturalHeight||C.height):typeof VideoFrame<"u"&&C instanceof VideoFrame?(c.width=C.displayWidth,c.height=C.displayHeight):(c.width=C.width,c.height=C.height),c}this.allocateTextureUnit=V,this.resetTextureUnits=B,this.getTextureUnits=F,this.setTextureUnits=P,this.setTexture2D=X,this.setTexture2DArray=G,this.setTexture3D=Y,this.setTextureCube=tt,this.rebindTextures=ne,this.setupRenderTarget=Kt,this.updateRenderTargetMipmap=te,this.updateMultisampleRenderTarget=Ne,this.setupDepthRenderbuffer=Qt,this.setupFrameBufferTexture=Rt,this.useMultisampledRTT=Ee,this.isReversedDepthBuffer=function(){return e.buffers.depth.getReversed()}}function jx(i,t){function e(n,s=Wi){let r,a=me.getTransfer(s);if(n===An)return i.UNSIGNED_BYTE;if(n===Go)return i.UNSIGNED_SHORT_4_4_4_4;if(n===Wo)return i.UNSIGNED_SHORT_5_5_5_1;if(n===Gc)return i.UNSIGNED_INT_5_9_9_9_REV;if(n===Wc)return i.UNSIGNED_INT_10F_11F_11F_REV;if(n===Hc)return i.BYTE;if(n===Vc)return i.SHORT;if(n===Ar)return i.UNSIGNED_SHORT;if(n===Vo)return i.INT;if(n===ri)return i.UNSIGNED_INT;if(n===Vn)return i.FLOAT;if(n===ai)return i.HALF_FLOAT;if(n===Xc)return i.ALPHA;if(n===qc)return i.RGB;if(n===Gn)return i.RGBA;if(n===xi)return i.DEPTH_COMPONENT;if(n===xs)return i.DEPTH_STENCIL;if(n===Xo)return i.RED;if(n===qo)return i.RED_INTEGER;if(n===_s)return i.RG;if(n===Yo)return i.RG_INTEGER;if(n===Zo)return i.RGBA_INTEGER;if(n===Ma||n===Sa||n===Ea||n===wa)if(a===we)if(r=t.get("WEBGL_compressed_texture_s3tc_srgb"),r!==null){if(n===Ma)return r.COMPRESSED_SRGB_S3TC_DXT1_EXT;if(n===Sa)return r.COMPRESSED_SRGB_ALPHA_S3TC_DXT1_EXT;if(n===Ea)return r.COMPRESSED_SRGB_ALPHA_S3TC_DXT3_EXT;if(n===wa)return r.COMPRESSED_SRGB_ALPHA_S3TC_DXT5_EXT}else return null;else if(r=t.get("WEBGL_compressed_texture_s3tc"),r!==null){if(n===Ma)return r.COMPRESSED_RGB_S3TC_DXT1_EXT;if(n===Sa)return r.COMPRESSED_RGBA_S3TC_DXT1_EXT;if(n===Ea)return r.COMPRESSED_RGBA_S3TC_DXT3_EXT;if(n===wa)return r.COMPRESSED_RGBA_S3TC_DXT5_EXT}else return null;if(n===$o||n===Ko||n===Jo||n===jo)if(r=t.get("WEBGL_compressed_texture_pvrtc"),r!==null){if(n===$o)return r.COMPRESSED_RGB_PVRTC_4BPPV1_IMG;if(n===Ko)return r.COMPRESSED_RGB_PVRTC_2BPPV1_IMG;if(n===Jo)return r.COMPRESSED_RGBA_PVRTC_4BPPV1_IMG;if(n===jo)return r.COMPRESSED_RGBA_PVRTC_2BPPV1_IMG}else return null;if(n===Qo||n===tl||n===el||n===nl||n===il||n===Ta||n===sl)if(r=t.get("WEBGL_compressed_texture_etc"),r!==null){if(n===Qo||n===tl)return a===we?r.COMPRESSED_SRGB8_ETC2:r.COMPRESSED_RGB8_ETC2;if(n===el)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ETC2_EAC:r.COMPRESSED_RGBA8_ETC2_EAC;if(n===nl)return r.COMPRESSED_R11_EAC;if(n===il)return r.COMPRESSED_SIGNED_R11_EAC;if(n===Ta)return r.COMPRESSED_RG11_EAC;if(n===sl)return r.COMPRESSED_SIGNED_RG11_EAC}else return null;if(n===rl||n===al||n===ol||n===ll||n===cl||n===hl||n===ul||n===dl||n===fl||n===pl||n===ml||n===gl||n===xl||n===_l)if(r=t.get("WEBGL_compressed_texture_astc"),r!==null){if(n===rl)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_4x4_KHR:r.COMPRESSED_RGBA_ASTC_4x4_KHR;if(n===al)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_5x4_KHR:r.COMPRESSED_RGBA_ASTC_5x4_KHR;if(n===ol)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_5x5_KHR:r.COMPRESSED_RGBA_ASTC_5x5_KHR;if(n===ll)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_6x5_KHR:r.COMPRESSED_RGBA_ASTC_6x5_KHR;if(n===cl)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR:r.COMPRESSED_RGBA_ASTC_6x6_KHR;if(n===hl)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_8x5_KHR:r.COMPRESSED_RGBA_ASTC_8x5_KHR;if(n===ul)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_8x6_KHR:r.COMPRESSED_RGBA_ASTC_8x6_KHR;if(n===dl)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_8x8_KHR:r.COMPRESSED_RGBA_ASTC_8x8_KHR;if(n===fl)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x5_KHR:r.COMPRESSED_RGBA_ASTC_10x5_KHR;if(n===pl)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x6_KHR:r.COMPRESSED_RGBA_ASTC_10x6_KHR;if(n===ml)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x8_KHR:r.COMPRESSED_RGBA_ASTC_10x8_KHR;if(n===gl)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_10x10_KHR:r.COMPRESSED_RGBA_ASTC_10x10_KHR;if(n===xl)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_12x10_KHR:r.COMPRESSED_RGBA_ASTC_12x10_KHR;if(n===_l)return a===we?r.COMPRESSED_SRGB8_ALPHA8_ASTC_12x12_KHR:r.COMPRESSED_RGBA_ASTC_12x12_KHR}else return null;if(n===yl||n===vl||n===bl)if(r=t.get("EXT_texture_compression_bptc"),r!==null){if(n===yl)return a===we?r.COMPRESSED_SRGB_ALPHA_BPTC_UNORM_EXT:r.COMPRESSED_RGBA_BPTC_UNORM_EXT;if(n===vl)return r.COMPRESSED_RGB_BPTC_SIGNED_FLOAT_EXT;if(n===bl)return r.COMPRESSED_RGB_BPTC_UNSIGNED_FLOAT_EXT}else return null;if(n===Ml||n===Sl||n===Aa||n===El)if(r=t.get("EXT_texture_compression_rgtc"),r!==null){if(n===Ml)return r.COMPRESSED_RED_RGTC1_EXT;if(n===Sl)return r.COMPRESSED_SIGNED_RED_RGTC1_EXT;if(n===Aa)return r.COMPRESSED_RED_GREEN_RGTC2_EXT;if(n===El)return r.COMPRESSED_SIGNED_RED_GREEN_RGTC2_EXT}else return null;return n===Rr?i.UNSIGNED_INT_24_8:i[n]!==void 0?i[n]:null}return{convert:e}}var Qx=`
void main() {

	gl_Position = vec4( position, 1.0 );

}`,t_=`
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

}`,_h=class{constructor(){this.texture=null,this.mesh=null,this.depthNear=0,this.depthFar=0}init(t,e){if(this.texture===null){let n=new ua(t.texture);(t.depthNear!==e.depthNear||t.depthFar!==e.depthFar)&&(this.depthNear=t.depthNear,this.depthFar=t.depthFar),this.texture=n}}getMesh(t){if(this.texture!==null&&this.mesh===null){let e=t.cameras[0].viewport,n=new Nn({vertexShader:Qx,fragmentShader:t_,uniforms:{depthColor:{value:this.texture},depthWidth:{value:e.z},depthHeight:{value:e.w}}});this.mesh=new Xt(new Ns(20,20),n)}return this.mesh}reset(){this.texture=null,this.mesh=null}getDepthTexture(){return this.texture}},yh=class extends ii{constructor(t,e){super();let n=this,s=null,r=1,a=null,o="local-floor",l=1,c=null,h=null,p=null,d=null,f=null,_=null,b=typeof XRWebGLBinding<"u",m=new _h,u={},S=e.getContextAttributes(),R=null,v=null,M=[],E=[],A=new qt,g=null,w=null,T=new Ye;T.viewport=new Oe;let I=new Ye;I.viewport=new Oe;let N=[T,I],B=new Fo,F=null,P=null;this.cameraAutoUpdate=!0,this.enabled=!1,this.isPresenting=!1,this.getController=function(q){let it=M[q];return it===void 0&&(it=new yr,M[q]=it),it.getTargetRaySpace()},this.getControllerGrip=function(q){let it=M[q];return it===void 0&&(it=new yr,M[q]=it),it.getGripSpace()},this.getHand=function(q){let it=M[q];return it===void 0&&(it=new yr,M[q]=it),it.getHandSpace()};function V(q){let it=E.indexOf(q.inputSource);if(it===-1)return;let gt=M[it];gt!==void 0&&(gt.update(q.inputSource,q.frame,c||a),gt.dispatchEvent({type:q.type,data:q.inputSource}))}function z(){s.removeEventListener("select",V),s.removeEventListener("selectstart",V),s.removeEventListener("selectend",V),s.removeEventListener("squeeze",V),s.removeEventListener("squeezestart",V),s.removeEventListener("squeezeend",V),s.removeEventListener("end",z),s.removeEventListener("inputsourceschange",X);for(let q=0;q<M.length;q++){let it=E[q];it!==null&&(E[q]=null,M[q].disconnect(it))}F=null,P=null,m.reset();for(let q in u)delete u[q];if(t.setRenderTarget(R),f=null,d=null,p=null,s=null,v=null,xt.stop(),n.isPresenting=!1,t.setPixelRatio(g),t.setSize(A.width,A.height,!1),w!==null){let q=w.camera;q.fov=w.fov,q.zoom=w.zoom,q.updateProjectionMatrix(),w=null}n.dispatchEvent({type:"sessionend"})}this.setFramebufferScaleFactor=function(q){r=q,n.isPresenting===!0&&Zt("WebXRManager: Cannot change framebuffer scale while presenting.")},this.setReferenceSpaceType=function(q){o=q,n.isPresenting===!0&&Zt("WebXRManager: Cannot change reference space type while presenting.")},this.getReferenceSpace=function(){return c||a},this.setReferenceSpace=function(q){c=q},this.getBaseLayer=function(){return d!==null?d:f},this.getBinding=function(){return p===null&&b&&(p=new XRWebGLBinding(s,e)),p},this.getFrame=function(){return _},this.getSession=function(){return s},this.setSession=async function(q){if(s=q,s!==null){if(R=t.getRenderTarget(),s.addEventListener("select",V),s.addEventListener("selectstart",V),s.addEventListener("selectend",V),s.addEventListener("squeeze",V),s.addEventListener("squeezestart",V),s.addEventListener("squeezeend",V),s.addEventListener("end",z),s.addEventListener("inputsourceschange",X),S.xrCompatible!==!0&&await e.makeXRCompatible(),g=t.getPixelRatio(),t.getSize(A),b&&"createProjectionLayer"in XRWebGLBinding.prototype){let gt=null,zt=null,Rt=null;S.depth&&(Rt=S.stencil?e.DEPTH24_STENCIL8:e.DEPTH_COMPONENT24,gt=S.stencil?xs:xi,zt=S.stencil?Rr:ri);let Yt={colorFormat:e.RGBA8,depthFormat:Rt,scaleFactor:r};p=this.getBinding(),d=p.createProjectionLayer(Yt),s.updateRenderState({layers:[d]}),t.setPixelRatio(1),t.setSize(d.textureWidth,d.textureHeight,!1),v=new wn(d.textureWidth,d.textureHeight,{format:Gn,type:An,depthTexture:new ls(d.textureWidth,d.textureHeight,zt,void 0,void 0,void 0,void 0,void 0,void 0,gt),stencilBuffer:S.stencil,colorSpace:t.outputColorSpace,samples:S.antialias?4:0,resolveDepthBuffer:d.ignoreDepthValues===!1,resolveStencilBuffer:d.ignoreDepthValues===!1,storeMultisampledDepthBuffer:d.ignoreDepthValues===!1,storeMultisampledStencilBuffer:d.ignoreDepthValues===!1})}else{let gt={antialias:S.antialias,alpha:!0,depth:S.depth,stencil:S.stencil,framebufferScaleFactor:r};f=new XRWebGLLayer(s,e,gt),s.updateRenderState({baseLayer:f}),t.setPixelRatio(1),t.setSize(f.framebufferWidth,f.framebufferHeight,!1),v=new wn(f.framebufferWidth,f.framebufferHeight,{format:Gn,type:An,colorSpace:t.outputColorSpace,stencilBuffer:S.stencil,resolveDepthBuffer:f.ignoreDepthValues===!1,resolveStencilBuffer:f.ignoreDepthValues===!1,storeMultisampledDepthBuffer:f.ignoreDepthValues===!1,storeMultisampledStencilBuffer:f.ignoreDepthValues===!1})}v.isXRRenderTarget=!0,this.setFoveation(l),c=null,a=await s.requestReferenceSpace(o),xt.setContext(s),xt.start(),n.isPresenting=!0,n.dispatchEvent({type:"sessionstart"})}},this.getEnvironmentBlendMode=function(){if(s!==null)return s.environmentBlendMode},this.getDepthTexture=function(){return m.getDepthTexture()};function X(q){for(let it=0;it<q.removed.length;it++){let gt=q.removed[it],zt=E.indexOf(gt);zt>=0&&(E[zt]=null,M[zt].disconnect(gt))}for(let it=0;it<q.added.length;it++){let gt=q.added[it],zt=E.indexOf(gt);if(zt===-1){for(let Yt=0;Yt<M.length;Yt++)if(Yt>=E.length){E.push(gt),zt=Yt;break}else if(E[Yt]===null){E[Yt]=gt,zt=Yt;break}if(zt===-1)break}let Rt=M[zt];Rt&&Rt.connect(gt)}}let G=new O,Y=new O;function tt(q,it,gt){G.setFromMatrixPosition(it.matrixWorld),Y.setFromMatrixPosition(gt.matrixWorld);let zt=G.distanceTo(Y),Rt=it.projectionMatrix.elements,Yt=gt.projectionMatrix.elements,Me=Rt[14]/(Rt[10]-1),Qt=Rt[14]/(Rt[10]+1),ne=(Rt[9]+1)/Rt[5],Kt=(Rt[9]-1)/Rt[5],te=(Rt[8]-1)/Rt[0],xe=(Yt[8]+1)/Yt[0],ze=Me*te,Ne=Me*xe,ge=zt/(-te+xe),Ee=ge*-te;if(it.matrixWorld.decompose(q.position,q.quaternion,q.scale),q.translateX(Ee),q.translateZ(ge),q.matrixWorld.compose(q.position,q.quaternion,q.scale),q.matrixWorldInverse.copy(q.matrixWorld).invert(),Rt[10]===-1)q.projectionMatrix.copy(it.projectionMatrix),q.projectionMatrixInverse.copy(it.projectionMatrixInverse);else{let W=Me+ge,Pe=Qt+ge,_e=ze-Ee,C=Ne+(zt-Ee),x=ne*Qt/Pe*W,K=Kt*Qt/Pe*W;q.projectionMatrix.makePerspective(_e,C,x,K,W,Pe),q.projectionMatrixInverse.copy(q.projectionMatrix).invert()}}function et(q,it){it===null?q.matrixWorld.copy(q.matrix):q.matrixWorld.multiplyMatrices(it.matrixWorld,q.matrix),q.matrixWorldInverse.copy(q.matrixWorld).invert()}this.updateCamera=function(q){if(s===null)return;let it=q.near,gt=q.far;m.texture!==null&&(m.depthNear>0&&(it=m.depthNear),m.depthFar>0&&(gt=m.depthFar)),B.near=I.near=T.near=it,B.far=I.far=T.far=gt,(F!==B.near||P!==B.far)&&(s.updateRenderState({depthNear:B.near,depthFar:B.far}),F=B.near,P=B.far),B.layers.mask=q.layers.mask|6,T.layers.mask=B.layers.mask&-5,I.layers.mask=B.layers.mask&-3;let zt=q.parent,Rt=B.cameras;et(B,zt);for(let Yt=0;Yt<Rt.length;Yt++)et(Rt[Yt],zt);Rt.length===2?tt(B,T,I):B.projectionMatrix.copy(T.projectionMatrix),w===null&&q.isPerspectiveCamera&&(w={camera:q,fov:q.fov,zoom:q.zoom}),dt(q,B,zt)};function dt(q,it,gt){gt===null?q.matrix.copy(it.matrixWorld):(q.matrix.copy(gt.matrixWorld),q.matrix.invert(),q.matrix.multiply(it.matrixWorld)),q.matrix.decompose(q.position,q.quaternion,q.scale),q.updateMatrixWorld(!0),q.projectionMatrix.copy(it.projectionMatrix),q.projectionMatrixInverse.copy(it.projectionMatrixInverse),q.isPerspectiveCamera&&(q.fov=gr*2*Math.atan(1/q.projectionMatrix.elements[5]),q.zoom=1)}this.getCamera=function(){return B},this.getFoveation=function(){if(!(d===null&&f===null))return l},this.setFoveation=function(q){l=q,d!==null&&(d.fixedFoveation=q),f!==null&&f.fixedFoveation!==void 0&&(f.fixedFoveation=q)},this.hasDepthSensing=function(){return m.texture!==null},this.getDepthSensingMesh=function(){return m.getMesh(B)},this.getCameraTexture=function(q){return u[q]};let Dt=null;function Pt(q,it){if(h=it.getViewerPose(c||a),_=it,h!==null){let gt=h.views;f!==null&&(t.setRenderTargetFramebuffer(v,f.framebuffer),t.setRenderTarget(v));let zt=!1;gt.length!==B.cameras.length&&(B.cameras.length=0,zt=!0);for(let Qt=0;Qt<gt.length;Qt++){let ne=gt[Qt],Kt=null;if(f!==null)Kt=f.getViewport(ne);else{let xe=p.getViewSubImage(d,ne);Kt=xe.viewport,Qt===0&&(t.setRenderTargetTextures(v,xe.colorTexture,xe.depthStencilTexture),t.setRenderTarget(v))}let te=N[Qt];te===void 0&&(te=new Ye,te.layers.enable(Qt),te.viewport=new Oe,N[Qt]=te),te.matrix.fromArray(ne.transform.matrix),te.matrix.decompose(te.position,te.quaternion,te.scale),te.projectionMatrix.fromArray(ne.projectionMatrix),te.projectionMatrixInverse.copy(te.projectionMatrix).invert(),te.viewport.set(Kt.x,Kt.y,Kt.width,Kt.height),Qt===0&&(B.matrix.copy(te.matrix),B.matrix.decompose(B.position,B.quaternion,B.scale)),zt===!0&&B.cameras.push(te)}let Rt=s.enabledFeatures;if(Rt&&Rt.includes("depth-sensing")&&s.depthUsage=="gpu-optimized"&&b){p=n.getBinding();let Qt=p.getDepthInformation(gt[0]);Qt&&Qt.isValid&&Qt.texture&&m.init(Qt,s.renderState)}if(Rt&&Rt.includes("camera-access")&&b){t.state.unbindTexture(),p=n.getBinding();for(let Qt=0;Qt<gt.length;Qt++){let ne=gt[Qt].camera;if(ne){let Kt=u[ne];Kt||(Kt=new ua,u[ne]=Kt);let te=p.getCameraImage(ne);Kt.sourceTexture=te}}}}for(let gt=0;gt<M.length;gt++){let zt=E[gt],Rt=M[gt];zt!==null&&Rt!==void 0&&Rt.update(zt,it,c||a)}Dt&&Dt(q,it),it.detectedPlanes&&n.dispatchEvent({type:"planesdetected",data:it}),_=null}let xt=new bd;xt.setAnimationLoop(Pt),this.setAnimationLoop=function(q){Dt=q},this.dispose=function(){}}},e_=new be,Ad=new ee;Ad.set(-1,0,0,0,1,0,0,0,1);function n_(i,t){function e(m,u){m.matrixAutoUpdate===!0&&m.updateMatrix(),u.value.copy(m.matrix)}function n(m,u){u.color.getRGB(m.fogColor.value,Kc(i)),u.isFog?(m.fogNear.value=u.near,m.fogFar.value=u.far):u.isFogExp2&&(m.fogDensity.value=u.density)}function s(m,u,S,R,v){u.isNodeMaterial?u.uniformsNeedUpdate=!1:u.isMeshBasicMaterial?r(m,u):u.isMeshLambertMaterial?(r(m,u),u.envMap&&(m.envMapIntensity.value=u.envMapIntensity)):u.isMeshToonMaterial?(r(m,u),p(m,u)):u.isMeshPhongMaterial?(r(m,u),h(m,u),u.envMap&&(m.envMapIntensity.value=u.envMapIntensity)):u.isMeshStandardMaterial?(r(m,u),d(m,u),u.isMeshPhysicalMaterial&&f(m,u,v)):u.isMeshMatcapMaterial?(r(m,u),_(m,u)):u.isMeshDepthMaterial?r(m,u):u.isMeshDistanceMaterial?(r(m,u),b(m,u)):u.isMeshNormalMaterial?r(m,u):u.isLineBasicMaterial?(a(m,u),u.isLineDashedMaterial&&o(m,u)):u.isPointsMaterial?l(m,u,S,R):u.isSpriteMaterial?c(m,u):u.isShadowMaterial?(m.color.value.copy(u.color),m.opacity.value=u.opacity):u.isShaderMaterial&&(u.uniformsNeedUpdate=!1)}function r(m,u){m.opacity.value=u.opacity,u.color&&m.diffuse.value.copy(u.color),u.emissive&&m.emissive.value.copy(u.emissive).multiplyScalar(u.emissiveIntensity),u.map&&(m.map.value=u.map,e(u.map,m.mapTransform)),u.alphaMap&&(m.alphaMap.value=u.alphaMap,e(u.alphaMap,m.alphaMapTransform)),u.bumpMap&&(m.bumpMap.value=u.bumpMap,e(u.bumpMap,m.bumpMapTransform),m.bumpScale.value=u.bumpScale,u.side===bn&&(m.bumpScale.value*=-1)),u.normalMap&&(m.normalMap.value=u.normalMap,e(u.normalMap,m.normalMapTransform),m.normalScale.value.copy(u.normalScale),u.side===bn&&m.normalScale.value.negate()),u.displacementMap&&(m.displacementMap.value=u.displacementMap,e(u.displacementMap,m.displacementMapTransform),m.displacementScale.value=u.displacementScale,m.displacementBias.value=u.displacementBias),u.emissiveMap&&(m.emissiveMap.value=u.emissiveMap,e(u.emissiveMap,m.emissiveMapTransform)),u.specularMap&&(m.specularMap.value=u.specularMap,e(u.specularMap,m.specularMapTransform)),u.alphaTest>0&&(m.alphaTest.value=u.alphaTest);let S=t.get(u),R=S.envMap,v=S.envMapRotation;R&&(m.envMap.value=R,m.envMapRotation.value.setFromMatrix4(e_.makeRotationFromEuler(v)).transpose(),R.isCubeTexture&&R.isRenderTargetTexture===!1&&m.envMapRotation.value.premultiply(Ad),m.reflectivity.value=u.reflectivity,m.ior.value=u.ior,m.refractionRatio.value=u.refractionRatio),u.lightMap&&(m.lightMap.value=u.lightMap,m.lightMapIntensity.value=u.lightMapIntensity,e(u.lightMap,m.lightMapTransform)),u.aoMap&&(m.aoMap.value=u.aoMap,m.aoMapIntensity.value=u.aoMapIntensity,e(u.aoMap,m.aoMapTransform))}function a(m,u){m.diffuse.value.copy(u.color),m.opacity.value=u.opacity,u.map&&(m.map.value=u.map,e(u.map,m.mapTransform))}function o(m,u){m.dashSize.value=u.dashSize,m.totalSize.value=u.dashSize+u.gapSize,m.scale.value=u.scale}function l(m,u,S,R){m.diffuse.value.copy(u.color),m.opacity.value=u.opacity,m.size.value=u.size*S,m.scale.value=R*.5,u.map&&(m.map.value=u.map,e(u.map,m.uvTransform)),u.alphaMap&&(m.alphaMap.value=u.alphaMap,e(u.alphaMap,m.alphaMapTransform)),u.alphaTest>0&&(m.alphaTest.value=u.alphaTest)}function c(m,u){m.diffuse.value.copy(u.color),m.opacity.value=u.opacity,m.rotation.value=u.rotation,u.map&&(m.map.value=u.map,e(u.map,m.mapTransform)),u.alphaMap&&(m.alphaMap.value=u.alphaMap,e(u.alphaMap,m.alphaMapTransform)),u.alphaTest>0&&(m.alphaTest.value=u.alphaTest)}function h(m,u){m.specular.value.copy(u.specular),m.shininess.value=Math.max(u.shininess,1e-4)}function p(m,u){u.gradientMap&&(m.gradientMap.value=u.gradientMap)}function d(m,u){m.metalness.value=u.metalness,u.metalnessMap&&(m.metalnessMap.value=u.metalnessMap,e(u.metalnessMap,m.metalnessMapTransform)),m.roughness.value=u.roughness,u.roughnessMap&&(m.roughnessMap.value=u.roughnessMap,e(u.roughnessMap,m.roughnessMapTransform)),u.envMap&&(m.envMapIntensity.value=u.envMapIntensity)}function f(m,u,S){m.ior.value=u.ior,u.sheen>0&&(m.sheenColor.value.copy(u.sheenColor).multiplyScalar(u.sheen),m.sheenRoughness.value=u.sheenRoughness,u.sheenColorMap&&(m.sheenColorMap.value=u.sheenColorMap,e(u.sheenColorMap,m.sheenColorMapTransform)),u.sheenRoughnessMap&&(m.sheenRoughnessMap.value=u.sheenRoughnessMap,e(u.sheenRoughnessMap,m.sheenRoughnessMapTransform))),u.clearcoat>0&&(m.clearcoat.value=u.clearcoat,m.clearcoatRoughness.value=u.clearcoatRoughness,u.clearcoatMap&&(m.clearcoatMap.value=u.clearcoatMap,e(u.clearcoatMap,m.clearcoatMapTransform)),u.clearcoatRoughnessMap&&(m.clearcoatRoughnessMap.value=u.clearcoatRoughnessMap,e(u.clearcoatRoughnessMap,m.clearcoatRoughnessMapTransform)),u.clearcoatNormalMap&&(m.clearcoatNormalMap.value=u.clearcoatNormalMap,e(u.clearcoatNormalMap,m.clearcoatNormalMapTransform),m.clearcoatNormalScale.value.copy(u.clearcoatNormalScale),u.side===bn&&m.clearcoatNormalScale.value.negate())),u.dispersion>0&&(m.dispersion.value=u.dispersion),u.retroreflectivity>0&&(m.retroreflectivity.value=u.retroreflectivity),u.iridescence>0&&(m.iridescence.value=u.iridescence,m.iridescenceIOR.value=u.iridescenceIOR,m.iridescenceThicknessMinimum.value=u.iridescenceThicknessRange[0],m.iridescenceThicknessMaximum.value=u.iridescenceThicknessRange[1],u.iridescenceMap&&(m.iridescenceMap.value=u.iridescenceMap,e(u.iridescenceMap,m.iridescenceMapTransform)),u.iridescenceThicknessMap&&(m.iridescenceThicknessMap.value=u.iridescenceThicknessMap,e(u.iridescenceThicknessMap,m.iridescenceThicknessMapTransform))),u.transmission>0&&(m.transmission.value=u.transmission,m.transmissionSamplerMap.value=S.texture,m.transmissionSamplerSize.value.set(S.width,S.height),u.transmissionMap&&(m.transmissionMap.value=u.transmissionMap,e(u.transmissionMap,m.transmissionMapTransform)),m.thickness.value=u.thickness,u.thicknessMap&&(m.thicknessMap.value=u.thicknessMap,e(u.thicknessMap,m.thicknessMapTransform)),m.attenuationDistance.value=u.attenuationDistance,m.attenuationColor.value.copy(u.attenuationColor)),u.anisotropy>0&&(m.anisotropyVector.value.set(u.anisotropy*Math.cos(u.anisotropyRotation),u.anisotropy*Math.sin(u.anisotropyRotation)),u.anisotropyMap&&(m.anisotropyMap.value=u.anisotropyMap,e(u.anisotropyMap,m.anisotropyMapTransform))),m.specularIntensity.value=u.specularIntensity,m.specularColor.value.copy(u.specularColor),u.specularColorMap&&(m.specularColorMap.value=u.specularColorMap,e(u.specularColorMap,m.specularColorMapTransform)),u.specularIntensityMap&&(m.specularIntensityMap.value=u.specularIntensityMap,e(u.specularIntensityMap,m.specularIntensityMapTransform))}function _(m,u){u.matcap&&(m.matcap.value=u.matcap)}function b(m,u){let S=t.get(u).light;m.referencePosition.value.setFromMatrixPosition(S.matrixWorld),m.nearDistance.value=S.shadow.camera.near,m.farDistance.value=S.shadow.camera.far}return{refreshFogUniforms:n,refreshMaterialUniforms:s}}function i_(i,t,e,n){let s={},r={},a=[],o=i.getParameter(i.MAX_UNIFORM_BUFFER_BINDINGS);function l(v,M){let E=M.program;n.uniformBlockBinding(v,E)}function c(v,M){let E=s[v.id];E===void 0&&(m(v),E=h(v),s[v.id]=E,v.addEventListener("dispose",S));let A=M.program;n.updateUBOMapping(v,A);let g=t.render.frame;r[v.id]!==g&&(d(v),r[v.id]=g)}function h(v){let M=p();v.__bindingPointIndex=M;let E=i.createBuffer(),A=v.__size,g=v.usage;return i.bindBuffer(i.UNIFORM_BUFFER,E),i.bufferData(i.UNIFORM_BUFFER,A,g),i.bindBuffer(i.UNIFORM_BUFFER,null),i.bindBufferBase(i.UNIFORM_BUFFER,M,E),E}function p(){for(let v=0;v<o;v++)if(a.indexOf(v)===-1)return a.push(v),v;return $t("WebGLRenderer: Maximum number of simultaneously usable uniforms groups reached."),0}function d(v){let M=s[v.id],E=v.uniforms,A=v.__cache;i.bindBuffer(i.UNIFORM_BUFFER,M);for(let g=0,w=E.length;g<w;g++){let T=E[g];if(Array.isArray(T))for(let I=0,N=T.length;I<N;I++)f(T[I],g,I,A);else f(T,g,0,A)}i.bindBuffer(i.UNIFORM_BUFFER,null)}function f(v,M,E,A){if(b(v,M,E,A)===!0){let g=v.__offset,w=v.value;if(Array.isArray(w)){let T=0;for(let I=0;I<w.length;I++){let N=w[I],B=u(N);_(N,v.__data,T),typeof N!="number"&&typeof N!="boolean"&&!N.isMatrix3&&!ArrayBuffer.isView(N)&&(T+=B.storage/Float32Array.BYTES_PER_ELEMENT)}}else _(w,v.__data,0);i.bufferSubData(i.UNIFORM_BUFFER,g,v.__data)}}function _(v,M,E){typeof v=="number"||typeof v=="boolean"?M[0]=v:v.isMatrix3?(M[0]=v.elements[0],M[1]=v.elements[1],M[2]=v.elements[2],M[3]=0,M[4]=v.elements[3],M[5]=v.elements[4],M[6]=v.elements[5],M[7]=0,M[8]=v.elements[6],M[9]=v.elements[7],M[10]=v.elements[8],M[11]=0):ArrayBuffer.isView(v)?M.set(new v.constructor(v.buffer,v.byteOffset,M.length)):v.toArray(M,E)}function b(v,M,E,A){let g=v.value,w=M+"_"+E;if(A[w]===void 0)return typeof g=="number"||typeof g=="boolean"?A[w]=g:ArrayBuffer.isView(g)?A[w]=g.slice():A[w]=g.clone(),!0;{let T=A[w];if(typeof g=="number"||typeof g=="boolean"){if(T!==g)return A[w]=g,!0}else{if(ArrayBuffer.isView(g))return!0;if(T.equals(g)===!1)return T.copy(g),!0}}return!1}function m(v){let M=v.uniforms,E=0,A=16;for(let w=0,T=M.length;w<T;w++){let I=Array.isArray(M[w])?M[w]:[M[w]];for(let N=0,B=I.length;N<B;N++){let F=I[N],P=Array.isArray(F.value)?F.value:[F.value];for(let V=0,z=P.length;V<z;V++){let X=P[V],G=u(X),Y=E%A,tt=Y%G.boundary,et=Y+tt;E+=tt,et!==0&&A-et<G.storage&&(E+=A-et),F.__data=new Float32Array(G.storage/Float32Array.BYTES_PER_ELEMENT),F.__offset=E,E+=G.storage}}}let g=E%A;return g>0&&(E+=A-g),v.__size=E,v.__cache={},this}function u(v){let M={boundary:0,storage:0};return typeof v=="number"||typeof v=="boolean"?(M.boundary=4,M.storage=4):v.isVector2?(M.boundary=8,M.storage=8):v.isVector3||v.isColor?(M.boundary=16,M.storage=12):v.isVector4?(M.boundary=16,M.storage=16):v.isMatrix3?(M.boundary=48,M.storage=48):v.isMatrix4?(M.boundary=64,M.storage=64):v.isTexture?Zt("WebGLRenderer: Texture samplers can not be part of an uniforms group."):ArrayBuffer.isView(v)?(M.boundary=16,M.storage=v.byteLength):Zt("WebGLRenderer: Unsupported uniform value type.",v),M}function S(v){let M=v.target;M.removeEventListener("dispose",S);let E=a.indexOf(M.__bindingPointIndex);a.splice(E,1),i.deleteBuffer(s[M.id]),delete s[M.id],delete r[M.id]}function R(){for(let v in s)i.deleteBuffer(s[v]);a=[],s={},r={}}return{bind:l,update:c,dispose:R}}var s_=new Uint16Array([12469,15057,12620,14925,13266,14620,13807,14376,14323,13990,14545,13625,14713,13328,14840,12882,14931,12528,14996,12233,15039,11829,15066,11525,15080,11295,15085,10976,15082,10705,15073,10495,13880,14564,13898,14542,13977,14430,14158,14124,14393,13732,14556,13410,14702,12996,14814,12596,14891,12291,14937,11834,14957,11489,14958,11194,14943,10803,14921,10506,14893,10278,14858,9960,14484,14039,14487,14025,14499,13941,14524,13740,14574,13468,14654,13106,14743,12678,14818,12344,14867,11893,14889,11509,14893,11180,14881,10751,14852,10428,14812,10128,14765,9754,14712,9466,14764,13480,14764,13475,14766,13440,14766,13347,14769,13070,14786,12713,14816,12387,14844,11957,14860,11549,14868,11215,14855,10751,14825,10403,14782,10044,14729,9651,14666,9352,14599,9029,14967,12835,14966,12831,14963,12804,14954,12723,14936,12564,14917,12347,14900,11958,14886,11569,14878,11247,14859,10765,14828,10401,14784,10011,14727,9600,14660,9289,14586,8893,14508,8533,15111,12234,15110,12234,15104,12216,15092,12156,15067,12010,15028,11776,14981,11500,14942,11205,14902,10752,14861,10393,14812,9991,14752,9570,14682,9252,14603,8808,14519,8445,14431,8145,15209,11449,15208,11451,15202,11451,15190,11438,15163,11384,15117,11274,15055,10979,14994,10648,14932,10343,14871,9936,14803,9532,14729,9218,14645,8742,14556,8381,14461,8020,14365,7603,15273,10603,15272,10607,15267,10619,15256,10631,15231,10614,15182,10535,15118,10389,15042,10167,14963,9787,14883,9447,14800,9115,14710,8665,14615,8318,14514,7911,14411,7507,14279,7198,15314,9675,15313,9683,15309,9712,15298,9759,15277,9797,15229,9773,15166,9668,15084,9487,14995,9274,14898,8910,14800,8539,14697,8234,14590,7790,14479,7409,14367,7067,14178,6621,15337,8619,15337,8631,15333,8677,15325,8769,15305,8871,15264,8940,15202,8909,15119,8775,15022,8565,14916,8328,14804,8009,14688,7614,14569,7287,14448,6888,14321,6483,14088,6171,15350,7402,15350,7419,15347,7480,15340,7613,15322,7804,15287,7973,15229,8057,15148,8012,15046,7846,14933,7611,14810,7357,14682,7069,14552,6656,14421,6316,14251,5948,14007,5528,15356,5942,15356,5977,15353,6119,15348,6294,15332,6551,15302,6824,15249,7044,15171,7122,15070,7050,14949,6861,14818,6611,14679,6349,14538,6067,14398,5651,14189,5311,13935,4958,15359,4123,15359,4153,15356,4296,15353,4646,15338,5160,15311,5508,15263,5829,15188,6042,15088,6094,14966,6001,14826,5796,14678,5543,14527,5287,14377,4985,14133,4586,13869,4257,15360,1563,15360,1642,15358,2076,15354,2636,15341,3350,15317,4019,15273,4429,15203,4732,15105,4911,14981,4932,14836,4818,14679,4621,14517,4386,14359,4156,14083,3795,13808,3437,15360,122,15360,137,15358,285,15355,636,15344,1274,15322,2177,15281,2765,15215,3223,15120,3451,14995,3569,14846,3567,14681,3466,14511,3305,14344,3121,14037,2800,13753,2467,15360,0,15360,1,15359,21,15355,89,15346,253,15325,479,15287,796,15225,1148,15133,1492,15008,1749,14856,1882,14685,1886,14506,1783,14324,1608,13996,1398,13702,1183]),Mi=null;function r_(){return Mi===null&&(Mi=new ca(s_,16,16,_s,ai),Mi.name="DFG_LUT",Mi.minFilter=ln,Mi.magFilter=ln,Mi.wrapS=mi,Mi.wrapT=mi,Mi.generateMipmaps=!1,Mi.needsUpdate=!0),Mi}var Dr=class{constructor(t={}){let{canvas:e=qu(),context:n=null,depth:s=!0,stencil:r=!1,alpha:a=!1,antialias:o=!1,premultipliedAlpha:l=!0,preserveDrawingBuffer:c=!1,powerPreference:h="default",failIfMajorPerformanceCaveat:p=!1,reversedDepthBuffer:d=!1,outputBufferType:f=An}=t;this.isWebGLRenderer=!0;let _;if(n!==null){if(typeof WebGLRenderingContext<"u"&&n instanceof WebGLRenderingContext)throw new Error("THREE.WebGLRenderer: WebGL 1 is not supported since r163.");_=n.getContextAttributes().alpha}else _=a;let b=f,m=new Set([Zo,Yo,qo]),u=new Set([An,ri,Ar,Rr,Go,Wo]),S=new Uint32Array(4),R=new Int32Array(4),v=new O,M=null,E=null,A=[],g=[],w=null;this.domElement=e,this.debug={checkShaderErrors:!0,diagnostics:{keywords:!1},onShaderError:null},this.autoClear=!0,this.autoClearColor=!0,this.autoClearDepth=!0,this.autoClearStencil=!0,this.sortObjects=!0,this.clippingPlanes=[],this.localClippingEnabled=!1,this.toneMapping=si,this.toneMappingExposure=1,this.transmissionResolutionScale=1;let T=this,I=!1,N=null,B=null,F=null,P=null;this._outputColorSpace=He;let V=0,z=0,X=null,G=-1,Y=null,tt=new Oe,et=new Oe,dt=null,Dt=new jt(0),Pt=0,xt=e.width,q=e.height,it=1,gt=null,zt=null,Rt=new Oe(0,0,xt,q),Yt=new Oe(0,0,xt,q),Me=!1,Qt=new br,ne=!1,Kt=!1,te=new be,xe=new O,ze=new Oe,Ne={background:null,fog:null,environment:null,overrideMaterial:null,isScene:!0},ge=!1;function Ee(){return X===null?it:1}let W=n;function Pe(y,D){return e.getContext(y,D)}let _e,C,x,K,j,ot,yt,bt,at,lt,Tt,J,nt,rt,pt,ct,vt,U,ft,st,_t,Mt,ut;try{let y={alpha:!0,depth:s,stencil:r,antialias:o,premultipliedAlpha:l,preserveDrawingBuffer:c,powerPreference:h,failIfMajorPerformanceCaveat:p};if("setAttribute"in e&&e.setAttribute("data-engine",`three.js r${"186"}`),e.addEventListener("webglcontextlost",fe,!1),e.addEventListener("webglcontextrestored",ye,!1),e.addEventListener("webglcontextcreationerror",xn,!1),W===null){let D="webgl2";if(W=Pe(D,y),W===null)throw Pe(D)?new Error("THREE.WebGLRenderer: Error creating WebGL context with your selected attributes."):new Error("THREE.WebGLRenderer: Error creating WebGL context.")}Gt()}catch(y){throw e.removeEventListener("webglcontextlost",fe,!1),e.removeEventListener("webglcontextrestored",ye,!1),e.removeEventListener("webglcontextcreationerror",xn,!1),$t("WebGLRenderer: "+y.message),y}function Gt(){_e=new dg(W),_e.init(),_t=new jx(W,_e),C=new ng(W,_e,t,_t),x=new Kx(W,_e),C.reversedDepthBuffer&&d&&x.buffers.depth.setReversed(!0),B=W.createFramebuffer(),F=W.createFramebuffer(),P=W.createFramebuffer(),K=new mg(W),j=new Ux,ot=new Jx(W,_e,x,j,C,_t,K),yt=new ug(T),bt=new xp(W),Mt=new tg(W,bt),at=new fg(W,bt,K,Mt),lt=new xg(W,at,bt,Mt,K),U=new gg(W,C,ot),pt=new ig(j),Tt=new Nx(T,yt,_e,C,Mt,pt),J=new n_(T,j),nt=new Ox,rt=new Wx(_e),vt=new Q0(T,yt,x,lt,_,l),ct=new $x(T,lt,C),ut=new i_(W,K,C,x),ft=new eg(W,_e,K),st=new pg(W,_e,K),K.programs=Tt.programs,T.capabilities=C,T.extensions=_e,T.properties=j,T.renderLists=nt,T.shadowMap=ct,T.state=x,T.info=K}b!==An&&(w=new yg(b,e.width,e.height,o,s,r));let kt=new yh(T,W);this.xr=kt,this.getContext=function(){return W},this.getContextAttributes=function(){return W.getContextAttributes()},this.forceContextLoss=function(){let y=_e.get("WEBGL_lose_context");y&&y.loseContext()},this.forceContextRestore=function(){let y=_e.get("WEBGL_lose_context");y&&y.restoreContext()},this.getPixelRatio=function(){return it},this.setPixelRatio=function(y){y!==void 0&&(it=y,this.setSize(xt,q,!1))},this.getSize=function(y){return y.set(xt,q)},this.setSize=function(y,D,k=!0){if(kt.isPresenting){Zt("WebGLRenderer: Can't change size while VR device is presenting.");return}xt=y,q=D,e.width=Math.floor(y*it),e.height=Math.floor(D*it),k===!0&&(e.style.width=y+"px",e.style.height=D+"px"),w!==null&&w.setSize(e.width,e.height),this.setViewport(0,0,y,D)},this.getDrawingBufferSize=function(y){return y.set(xt*it,q*it).floor()},this.setDrawingBufferSize=function(y,D,k){xt=y,q=D,it=k,e.width=Math.floor(y*k),e.height=Math.floor(D*k),this.setViewport(0,0,y,D)},this.setEffects=function(y){if(b===An){$t("WebGLRenderer: setEffects() requires outputBufferType set to HalfFloatType or FloatType.");return}if(y){for(let D=0;D<y.length;D++)if(y[D].isOutputPass===!0){Zt("WebGLRenderer: OutputPass is not needed in setEffects(). Tone mapping and color space conversion are applied automatically.");break}}w.setEffects(y||[])},this.getCurrentViewport=function(y){return y.copy(tt)},this.getViewport=function(y){return y.copy(Rt)},this.setViewport=function(y,D,k,H){y.isVector4?Rt.set(y.x,y.y,y.z,y.w):Rt.set(y,D,k,H),x.viewport(tt.copy(Rt).multiplyScalar(it).round())},this.getScissor=function(y){return y.copy(Yt)},this.setScissor=function(y,D,k,H){y.isVector4?Yt.set(y.x,y.y,y.z,y.w):Yt.set(y,D,k,H),x.scissor(et.copy(Yt).multiplyScalar(it).round())},this.getScissorTest=function(){return Me},this.setScissorTest=function(y){x.setScissorTest(Me=y)},this.setOpaqueSort=function(y){gt=y},this.setTransparentSort=function(y){zt=y},this.getClearColor=function(y){return y.copy(vt.getClearColor())},this.setClearColor=function(){vt.setClearColor(...arguments)},this.getClearAlpha=function(){return vt.getClearAlpha()},this.setClearAlpha=function(){vt.setClearAlpha(...arguments)},this.clear=function(y=!0,D=!0,k=!0){let H=0;if(y){let $=!1;if(X!==null){let mt=X.texture.format;$=m.has(mt)}if($){let mt=X.texture.type,Ct=u.has(mt),wt=vt.getClearColor(),Ot=vt.getClearAlpha(),Vt=wt.r,Jt=wt.g,se=wt.b;Ct?(S[0]=Vt,S[1]=Jt,S[2]=se,S[3]=Ot,W.clearBufferuiv(W.COLOR,0,S)):(R[0]=Vt,R[1]=Jt,R[2]=se,R[3]=Ot,W.clearBufferiv(W.COLOR,0,R))}else H|=W.COLOR_BUFFER_BIT}D&&(H|=W.DEPTH_BUFFER_BIT,this.state.buffers.depth.setMask(!0)),k&&(H|=W.STENCIL_BUFFER_BIT,this.state.buffers.stencil.setMask(4294967295)),H!==0&&W.clear(H)},this.clearColor=function(){this.clear(!0,!1,!1)},this.clearDepth=function(){this.clear(!1,!0,!1)},this.clearStencil=function(){this.clear(!1,!1,!0)},this.setNodesHandler=function(y){y.setRenderer(this),N=y},this.dispose=function(){e.removeEventListener("webglcontextlost",fe,!1),e.removeEventListener("webglcontextrestored",ye,!1),e.removeEventListener("webglcontextcreationerror",xn,!1),vt.dispose(),nt.dispose(),rt.dispose(),j.dispose(),yt.dispose(),lt.dispose(),Mt.dispose(),ut.dispose(),Tt.dispose(),kt.dispose(),kt.removeEventListener("sessionstart",Li),kt.removeEventListener("sessionend",Ki),Di.stop()};function fe(y){y.preventDefault(),Zc("WebGLRenderer: Context Lost."),I=!0}function ye(){Zc("WebGLRenderer: Context Restored."),I=!1;let y=K.autoReset,D=ct.enabled,k=ct.autoUpdate,H=ct.needsUpdate,$=ct.type;Gt(),K.autoReset=y,ct.enabled=D,ct.autoUpdate=k,ct.needsUpdate=H,ct.type=$}function xn(y){$t("WebGLRenderer: A WebGL context could not be created. Reason: ",y.statusMessage)}function _n(y){let D=y.target;D.removeEventListener("dispose",_n),qr(D)}function qr(y){Ii(y),j.remove(y)}function Ii(y){let D=j.get(y).programs;D!==void 0&&(D.forEach(function(k){Tt.releaseProgram(k)}),y.isShaderMaterial&&Tt.releaseShaderCache(y))}this.renderBufferDirect=function(y,D,k,H,$,mt){D===null&&(D=Ne);let Ct=$.isMesh&&$.matrixWorld.determinantAffine()<0,wt=St(y,D,k,H,$);x.setMaterial(H,Ct);let Ot=k.index,Vt=1;if(H.wireframe===!0){if(Ot=at.getWireframeAttribute(k),Ot===void 0)return;Vt=2}let Jt=k.drawRange,se=k.attributes.position,Bt=Jt.start*Vt,ve=(Jt.start+Jt.count)*Vt;mt!==null&&(Bt=Math.max(Bt,mt.start*Vt),ve=Math.min(ve,(mt.start+mt.count)*Vt)),Ot!==null?(Bt=Math.max(Bt,0),ve=Math.min(ve,Ot.count)):se!=null&&(Bt=Math.max(Bt,0),ve=Math.min(ve,se.count));let Ie=ve-Bt;if(Ie<0||Ie===1/0)return;Mt.setup($,H,wt,k,Ot);let Ft,pe=ft;if(Ot!==null&&(Ft=bt.get(Ot),pe=st,pe.setIndex(Ft)),$.isMesh)H.wireframe===!0?(x.setLineWidth(H.wireframeLinewidth*Ee()),pe.setMode(W.LINES)):pe.setMode(W.TRIANGLES);else if($.isLine){let ke=H.linewidth;ke===void 0&&(ke=1),x.setLineWidth(ke*Ee()),$.isLineSegments?pe.setMode(W.LINES):$.isLineLoop?pe.setMode(W.LINE_LOOP):pe.setMode(W.LINE_STRIP)}else $.isPoints?pe.setMode(W.POINTS):$.isSprite&&pe.setMode(W.TRIANGLES);if($.isBatchedMesh)if(_e.get("WEBGL_multi_draw"))pe.renderMultiDraw($._multiDrawStarts,$._multiDrawCounts,$._multiDrawCount);else{let ke=$._multiDrawStarts,Nt=$._multiDrawCounts,je=$._multiDrawCount,ce=Ot?bt.get(Ot).bytesPerElement:1,kn=j.get(H).currentProgram.getUniforms();for(let fi=0;fi<je;fi++)kn.setValue(W,"_gl_DrawID",fi),pe.render(ke[fi]/ce,Nt[fi])}else if($.isInstancedMesh)pe.renderInstances(Bt,Ie,$.count);else if(k.isInstancedBufferGeometry){let ke=k._maxInstanceCount!==void 0?k._maxInstanceCount:1/0,Nt=Math.min(k.instanceCount,ke);pe.renderInstances(Bt,Ie,Nt)}else pe.render(Bt,Ie)};function Ys(y,D,k,H){N!==null&&y.isNodeMaterial&&N.setObject(H,y),ne===!0&&pt.setState(y,k,!1),y.transparent===!0&&y.side===vi&&y.forceSinglePass===!1?(y.side=bn,y.needsUpdate=!0,As(y,D,H),y.side=ps,y.needsUpdate=!0,As(y,D,H),y.side=vi):As(y,D,H)}this.compile=function(y,D,k=null){k===null&&(k=y),N!==null&&N.renderStart(y,D,k),E=rt.get(k),E.init(D),g.push(E),k.traverseVisible(function($){$.isLight&&$.layers.test(D.layers)&&(E.pushLight($),$.castShadow&&E.pushShadow($))}),y!==k&&y.traverseVisible(function($){$.isLight&&$.layers.test(D.layers)&&(E.pushLight($),$.castShadow&&E.pushShadow($))}),E.setupLights(),N!==null&&N.updateLights(E.state.lightsArray),Kt=this.localClippingEnabled,ne=pt.init(this.clippingPlanes,Kt),ne===!0&&pt.setGlobalState(this.clippingPlanes,D),N!==null&&ct.render(E.state.shadowsArray,k,D);let H=new Set;return y.traverse(function($){if(!($.isMesh||$.isPoints||$.isLine||$.isSprite))return;let mt=$.material;if(mt)if(Array.isArray(mt))for(let Ct=0;Ct<mt.length;Ct++){let wt=mt[Ct];Ys(wt,k,D,$),H.add(wt)}else Ys(mt,k,D,$),H.add(mt)}),E=g.pop(),N!==null&&N.renderEnd(),H},this.compileAsync=function(y,D,k=null){let H=this.compile(y,D,k);return new Promise($=>{function mt(){if(H.forEach(function(Ct){let Ot=j.get(Ct).currentProgram;(Ot===void 0||Ot.isReady())&&H.delete(Ct)}),H.size===0){$(y);return}setTimeout(mt,10)}_e.get("KHR_parallel_shader_compile")!==null?mt():setTimeout(mt,10)})};let Es=null;function $i(y){Es&&Es(y)}function Li(){Di.stop()}function Ki(){Di.start()}let Di=new bd;Di.setAnimationLoop($i),typeof self<"u"&&Di.setContext(self),this.setAnimationLoop=function(y){Es=y,kt.setAnimationLoop(y),y===null?Di.stop():Di.start()},kt.addEventListener("sessionstart",Li),kt.addEventListener("sessionend",Ki),this.render=function(y,D){if(D!==void 0&&D.isCamera!==!0){$t("WebGLRenderer.render: camera is not an instance of THREE.Camera.");return}if(I===!0)return;N!==null&&N.renderStart(y,D);let k=kt.enabled===!0&&kt.isPresenting===!0,H=w!==null&&(X===null||k)&&w.begin(T,X);if(y.matrixWorldAutoUpdate===!0&&y.updateMatrixWorld(),D.parent===null&&D.matrixWorldAutoUpdate===!0&&D.updateMatrixWorld(),kt.enabled===!0&&kt.isPresenting===!0&&(w===null||w.isCompositing()===!1)&&(kt.cameraAutoUpdate===!0&&kt.updateCamera(D),D=kt.getCamera()),y.isScene===!0&&y.onBeforeRender(T,y,D,X),E=rt.get(y,g.length),E.init(D),E.state.textureUnits=ot.getTextureUnits(),g.push(E),te.multiplyMatrices(D.projectionMatrix,D.matrixWorldInverse),Qt.setFromProjectionMatrix(te,ni,D.reversedDepth),Kt=this.localClippingEnabled,ne=pt.init(this.clippingPlanes,Kt),M=nt.get(y,A.length),M.init(),A.push(M),kt.enabled===!0&&kt.isPresenting===!0){let Ct=T.xr.getDepthSensingMesh();Ct!==null&&Zs(Ct,D,-1/0,T.sortObjects)}Zs(y,D,0,T.sortObjects),M.finish(),N!==null&&N.updateLights(E.state.lightsArray),T.sortObjects===!0&&M.sort(gt,zt),ge=kt.enabled===!1||kt.isPresenting===!1||kt.hasDepthSensing()===!1,ge&&vt.addToRenderList(M,y),this.info.render.frame++,this.info.autoReset===!0&&this.info.reset(),ne===!0&&pt.beginShadows();let $=E.state.shadowsArray;if(ct.render($,y,D),ne===!0&&pt.endShadows(),(H&&w.hasRenderPass())===!1){let Ct=M.opaque,wt=M.transmissive;if(E.setupLights(),D.isArrayCamera){let Ot=D.cameras;if(wt.length>0)for(let Vt=0,Jt=Ot.length;Vt<Jt;Vt++){let se=Ot[Vt];Yr(Ct,wt,y,se)}ge&&vt.render(y);for(let Vt=0,Jt=Ot.length;Vt<Jt;Vt++){let se=Ot[Vt];Pn(M,y,se,se.viewport)}}else wt.length>0&&Yr(Ct,wt,y,D),ge&&vt.render(y),Pn(M,y,D)}X!==null&&z===0&&(ot.updateMultisampleRenderTarget(X),ot.updateRenderTargetMipmap(X)),H&&w.end(T),y.isScene===!0&&y.onAfterRender(T,y,D),Mt.resetDefaultState(),G=-1,Y=null,g.pop(),g.length>0?(E=g[g.length-1],ot.setTextureUnits(E.state.textureUnits),ne===!0&&pt.setGlobalState(T.clippingPlanes,E.state.camera)):E=null,A.pop(),A.length>0?M=A[A.length-1]:M=null,N!==null&&N.renderEnd()};function Zs(y,D,k,H){if(y.visible===!1)return;if(y.layers.test(D.layers)){if(y.isGroup)k=y.renderOrder;else if(y.isLOD)y.autoUpdate===!0&&y.update(D);else if(y.isLightProbeGrid)E.pushLightProbeGrid(y);else if(y.isLight)E.pushLight(y),y.castShadow&&E.pushShadow(y);else if(y.isSprite){if(!y.frustumCulled||y.intersectsFrustum(Qt)){H&&ze.setFromMatrixPosition(y.matrixWorld).applyMatrix4(te);let Ct=lt.update(y),wt=y.material;wt.visible&&M.push(y,Ct,wt,k,ze.z,null,D)}}else if((y.isMesh||y.isLine||y.isPoints)&&(!y.frustumCulled||y.intersectsFrustum(Qt))){let Ct=lt.update(y),wt=y.material;if(H&&(y.boundingSphere!==void 0?(y.boundingSphere===null&&y.computeBoundingSphere(),ze.copy(y.boundingSphere.center)):(Ct.boundingSphere===null&&Ct.computeBoundingSphere(),ze.copy(Ct.boundingSphere.center)),ze.applyMatrix4(y.matrixWorld).applyMatrix4(te)),Array.isArray(wt)){let Ot=Ct.groups;for(let Vt=0,Jt=Ot.length;Vt<Jt;Vt++){let se=Ot[Vt],Bt=wt[se.materialIndex];Bt&&Bt.visible&&M.push(y,Ct,Bt,k,ze.z,se,D)}}else wt.visible&&M.push(y,Ct,wt,k,ze.z,null,D)}}let mt=y.children;for(let Ct=0,wt=mt.length;Ct<wt;Ct++)Zs(mt[Ct],D,k,H)}function Pn(y,D,k,H){let{opaque:$,transmissive:mt,transparent:Ct}=y;E.setupLightsView(k),ne===!0&&pt.setGlobalState(T.clippingPlanes,k),H&&x.viewport(tt.copy(H)),$.length>0&&ws($,D,k),mt.length>0&&ws(mt,D,k),Ct.length>0&&ws(Ct,D,k),x.buffers.depth.setTest(!0),x.buffers.depth.setMask(!0),x.buffers.color.setMask(!0),x.setPolygonOffset(!1)}function Yr(y,D,k,H){if((k.isScene===!0?k.overrideMaterial:null)!==null)return;if(E.state.transmissionRenderTarget[H.id]===void 0){let Bt=_e.has("EXT_color_buffer_half_float")||_e.has("EXT_color_buffer_float");E.state.transmissionRenderTarget[H.id]=new wn(1,1,{generateMipmaps:!0,type:Bt?ai:An,minFilter:gs,samples:Math.max(4,C.samples),stencilBuffer:r,resolveDepthBuffer:!1,resolveStencilBuffer:!1,storeMultisampledDepthBuffer:!1,storeMultisampledStencilBuffer:!1,colorSpace:me.workingColorSpace})}let mt=E.state.transmissionRenderTarget[H.id],Ct=H.viewport||tt;mt.setSize(Ct.z*T.transmissionResolutionScale,Ct.w*T.transmissionResolutionScale);let wt=T.getRenderTarget(),Ot=T.getActiveCubeFace(),Vt=T.getActiveMipmapLevel();T.setRenderTarget(mt),T.getClearColor(Dt),Pt=T.getClearAlpha(),Pt<1&&T.setClearColor(16777215,.5),T.clear(),ge&&vt.render(k);let Jt=T.toneMapping;T.toneMapping=si;let se=H.viewport;if(H.viewport!==void 0&&(H.viewport=void 0),E.setupLightsView(H),ne===!0&&pt.setGlobalState(T.clippingPlanes,H),ws(y,k,H),ot.updateMultisampleRenderTarget(mt),ot.updateRenderTargetMipmap(mt),_e.has("WEBGL_multisampled_render_to_texture")===!1){let Bt=!1;for(let ve=0,Ie=D.length;ve<Ie;ve++){let Ft=D[ve],{object:pe,geometry:ke,material:Nt,group:je}=Ft;if(Nt.side===vi&&pe.layers.test(H.layers)){let ce=Nt.side;Nt.side=bn,Nt.needsUpdate=!0,Ts(pe,k,H,ke,Nt,je),Nt.side=ce,Nt.needsUpdate=!0,Bt=!0}}Bt===!0&&(ot.updateMultisampleRenderTarget(mt),ot.updateRenderTargetMipmap(mt))}T.setRenderTarget(wt,Ot,Vt),T.setClearColor(Dt,Pt),se!==void 0&&(H.viewport=se),T.toneMapping=Jt}function ws(y,D,k){let H=D.isScene===!0?D.overrideMaterial:null;for(let $=0,mt=y.length;$<mt;$++){let Ct=y[$],{object:wt,geometry:Ot,group:Vt}=Ct,Jt=Ct.material;Jt.allowOverride===!0&&H!==null&&(Jt=H),wt.layers.test(k.layers)&&Ts(wt,D,k,Ot,Jt,Vt)}}function Ts(y,D,k,H,$,mt){N!==null&&$.isNodeMaterial&&N.setObject(y,$),y.onBeforeRender(T,D,k,H,$,mt),y.modelViewMatrix.multiplyMatrices(k.matrixWorldInverse,y.matrixWorld),y.normalMatrix.getNormalMatrix(y.modelViewMatrix),$.onBeforeRender(T,D,k,H,y,mt),$.transparent===!0&&$.side===vi&&$.forceSinglePass===!1?($.side=bn,$.needsUpdate=!0,T.renderBufferDirect(k,D,H,$,y,mt),$.side=ps,$.needsUpdate=!0,T.renderBufferDirect(k,D,H,$,y,mt),$.side=vi):T.renderBufferDirect(k,D,H,$,y,mt),y.onAfterRender(T,D,k,H,$,mt)}function As(y,D,k){D.isScene!==!0&&(D=Ne);let H=j.get(y),$=E.state.lights,mt=E.state.shadowsArray,Ct=$.state.version,wt=Tt.getParameters(y,$.state,mt,D,k,E.state.lightProbeGridArray),Ot=Tt.getProgramCacheKey(wt),Vt=H.programs;H.environment=y.isMeshStandardMaterial||y.isMeshLambertMaterial||y.isMeshPhongMaterial?D.environment:null,H.fog=D.fog;let Jt=y.isMeshStandardMaterial||y.isMeshLambertMaterial&&!y.envMap||y.isMeshPhongMaterial&&!y.envMap;H.envMap=yt.get(y.envMap||H.environment,Jt),H.envMapRotation=H.environment!==null&&y.envMap===null?D.environmentRotation:y.envMapRotation,Vt===void 0&&(y.addEventListener("dispose",_n),Vt=new Map,H.programs=Vt);let se=Vt.get(Ot);if(se!==void 0){if(H.currentProgram===se&&H.lightsStateVersion===Ct)return Q(y,wt),se}else wt.uniforms=Tt.getUniforms(y),N!==null&&y.isNodeMaterial&&N.build(y,k,wt),y.onBeforeCompile(wt,T),se=Tt.acquireProgram(wt,Ot),Vt.set(Ot,se),H.uniforms=wt.uniforms;let Bt=H.uniforms;return(!y.isShaderMaterial&&!y.isRawShaderMaterial||y.clipping===!0)&&(Bt.clippingPlanes=pt.uniform),Q(y,wt),H.needsLights=It(y),H.lightsStateVersion=Ct,H.needsLights&&(Bt.ambientLightColor.value=$.state.ambient,Bt.lightProbe.value=$.state.probe,Bt.sunLights.value=$.state.sun,Bt.sunLightShadows.value=$.state.sunShadow,Bt.directionalLights.value=$.state.directional,Bt.directionalLightShadows.value=$.state.directionalShadow,Bt.spotLights.value=$.state.spot,Bt.spotLightShadows.value=$.state.spotShadow,Bt.rectAreaLights.value=$.state.rectArea,Bt.ltc_1.value=$.state.rectAreaLTC1,Bt.ltc_2.value=$.state.rectAreaLTC2,Bt.pointLights.value=$.state.point,Bt.pointLightShadows.value=$.state.pointShadow,Bt.hemisphereLights.value=$.state.hemi,Bt.sunShadowMatrix.value=$.state.sunShadowMatrix,Bt.sunShadowCascade.value=$.state.sunShadowCascade,Bt.directionalShadowMatrix.value=$.state.directionalShadowMatrix,Bt.spotLightMatrix.value=$.state.spotLightMatrix,Bt.spotLightMap.value=$.state.spotLightMap,Bt.pointShadowMatrix.value=$.state.pointShadowMatrix),H.lightProbeGrid=E.state.lightProbeGridArray.length>0,H.currentProgram=se,H.uniformsList=null,se}function Z(y){if(y.uniformsList===null){let D=y.currentProgram.getUniforms();y.uniformsList=Lr.seqWithValue(D.seq,y.uniforms)}return y.uniformsList}function Q(y,D){let k=j.get(y);k.outputColorSpace=D.outputColorSpace,k.batching=D.batching,k.batchingColor=D.batchingColor,k.instancing=D.instancing,k.instancingColor=D.instancingColor,k.instancingMorph=D.instancingMorph,k.skinning=D.skinning,k.morphTargets=D.morphTargets,k.morphNormals=D.morphNormals,k.morphColors=D.morphColors,k.morphTargetsCount=D.morphTargetsCount,k.numClippingPlanes=D.numClippingPlanes,k.numIntersection=D.numClipIntersection,k.vertexAlphas=D.vertexAlphas,k.vertexTangents=D.vertexTangents,k.toneMapping=D.toneMapping}function ht(y,D){if(y.length===0)return null;if(y.length===1)return y[0].texture!==null?y[0]:null;v.setFromMatrixPosition(D.matrixWorld);for(let k=0,H=y.length;k<H;k++){let $=y[k];if($.texture!==null&&$.boundingBox.containsPoint(v))return $}return null}function St(y,D,k,H,$){D.isScene!==!0&&(D=Ne),ot.resetTextureUnits();let mt=D.fog,Ct=H.isMeshStandardMaterial||H.isMeshLambertMaterial||H.isMeshPhongMaterial?D.environment:null,wt=X===null?T.outputColorSpace:X.isXRRenderTarget===!0?X.texture.colorSpace:me.workingColorSpace,Ot=H.isMeshStandardMaterial||H.isMeshLambertMaterial&&!H.envMap||H.isMeshPhongMaterial&&!H.envMap,Vt=yt.get(H.envMap||Ct,Ot),Jt=H.vertexColors===!0&&!!k.attributes.color&&k.attributes.color.itemSize===4,se=!!k.attributes.tangent&&(!!H.normalMap||H.anisotropy>0),Bt=!!k.morphAttributes.position,ve=!!k.morphAttributes.normal,Ie=!!k.morphAttributes.color,Ft=si;H.toneMapped&&(X===null||X.isXRRenderTarget===!0)&&(Ft=T.toneMapping);let pe=k.morphAttributes.position||k.morphAttributes.normal||k.morphAttributes.color,ke=pe!==void 0?pe.length:0,Nt=j.get(H),je=E.state.lights;if(ne===!0&&(Kt===!0||y!==Y)){let Le=y===Y&&H.id===G;pt.setState(H,y,Le)}let ce=!1;H.version===Nt.__version?(Nt.needsLights&&Nt.lightsStateVersion!==je.state.version||Nt.outputColorSpace!==wt||$.isBatchedMesh&&Nt.batching===!1||!$.isBatchedMesh&&Nt.batching===!0||$.isBatchedMesh&&Nt.batchingColor===!0&&$._colorsTexture===null||$.isBatchedMesh&&Nt.batchingColor===!1&&$._colorsTexture!==null||$.isInstancedMesh&&Nt.instancing===!1||!$.isInstancedMesh&&Nt.instancing===!0||$.isSkinnedMesh&&Nt.skinning===!1||!$.isSkinnedMesh&&Nt.skinning===!0||$.isInstancedMesh&&Nt.instancingColor===!0&&$.instanceColor===null||$.isInstancedMesh&&Nt.instancingColor===!1&&$.instanceColor!==null||$.isInstancedMesh&&Nt.instancingMorph===!0&&$.morphTexture===null||$.isInstancedMesh&&Nt.instancingMorph===!1&&$.morphTexture!==null||Nt.envMap!==Vt||H.fog===!0&&Nt.fog!==mt||Nt.numClippingPlanes!==void 0&&(Nt.numClippingPlanes!==pt.numPlanes||Nt.numIntersection!==pt.numIntersection)||Nt.vertexAlphas!==Jt||Nt.vertexTangents!==se||Nt.morphTargets!==Bt||Nt.morphNormals!==ve||Nt.morphColors!==Ie||Nt.toneMapping!==Ft||Nt.morphTargetsCount!==ke||!!Nt.lightProbeGrid!=E.state.lightProbeGridArray.length>0)&&(ce=!0):(ce=!0,Nt.__version=H.version);let kn=Nt.currentProgram;ce===!0&&(kn=As(H,D,$),N&&H.isNodeMaterial&&N.onUpdateProgram(H,kn,Nt));let fi=!1,Ji=!1,$s=!1,Ce=kn.getUniforms(),Ge=Nt.uniforms;if(x.useProgram(kn.program)&&(fi=!0,Ji=!0,$s=!0),H.id!==G&&(G=H.id,Ji=!0),Nt.needsLights){let Le=ht(E.state.lightProbeGridArray,$);Nt.lightProbeGrid!==Le&&(Nt.lightProbeGrid=Le,Ji=!0)}if(fi||Y!==y){x.buffers.depth.getReversed()&&y.reversedDepth!==!0&&(y._reversedDepth=!0,y.updateProjectionMatrix()),Ce.setValue(W,"projectionMatrix",y.projectionMatrix),Ce.setValue(W,"viewMatrix",y.matrixWorldInverse);let Qi=Ce.map.cameraPosition;Qi!==void 0&&Qi.setValue(W,xe.setFromMatrixPosition(y.matrixWorld)),C.logarithmicDepthBuffer&&Ce.setValue(W,"logDepthBufFC",2/(Math.log(y.far+1)/Math.LN2)),(H.isMeshPhongMaterial||H.isMeshToonMaterial||H.isMeshLambertMaterial||H.isMeshBasicMaterial||H.isMeshStandardMaterial||H.isShaderMaterial)&&Ce.setValue(W,"isOrthographic",y.isOrthographicCamera===!0),Y!==y&&(Y=y,Ji=!0,$s=!0)}if(Nt.needsLights&&(je.state.sunShadowMap.length>0&&Ce.setValue(W,"sunShadowMap",je.state.sunShadowMap,ot),je.state.directionalShadowMap.length>0&&Ce.setValue(W,"directionalShadowMap",je.state.directionalShadowMap,ot),je.state.spotShadowMap.length>0&&Ce.setValue(W,"spotShadowMap",je.state.spotShadowMap,ot),je.state.pointShadowMap.length>0&&Ce.setValue(W,"pointShadowMap",je.state.pointShadowMap,ot)),$.isSkinnedMesh){Ce.setOptional(W,$,"bindMatrix"),Ce.setOptional(W,$,"bindMatrixInverse");let Le=$.skeleton;Le&&(Le.boneTexture===null&&Le.computeBoneTexture(),Ce.setValue(W,"boneTexture",Le.boneTexture,ot))}$.isBatchedMesh&&(Ce.setOptional(W,$,"batchingTexture"),Ce.setValue(W,"batchingTexture",$._matricesTexture,ot),Ce.setOptional(W,$,"batchingIdTexture"),Ce.setValue(W,"batchingIdTexture",$._indirectTexture,ot),Ce.setOptional(W,$,"batchingColorTexture"),$._colorsTexture!==null&&Ce.setValue(W,"batchingColorTexture",$._colorsTexture,ot));let ji=k.morphAttributes;if((ji.position!==void 0||ji.normal!==void 0||ji.color!==void 0)&&U.update($,k,kn),(Ji||Nt.receiveShadow!==$.receiveShadow)&&(Nt.receiveShadow=$.receiveShadow,Ce.setValue(W,"receiveShadow",$.receiveShadow)),(H.isMeshStandardMaterial||H.isMeshLambertMaterial||H.isMeshPhongMaterial)&&H.envMap===null&&D.environment!==null&&(Ge.envMapIntensity.value=D.environmentIntensity),Ge.dfgLUT!==void 0&&(Ge.dfgLUT.value=r_()),Ji){if(Ce.setValue(W,"toneMappingExposure",T.toneMappingExposure),Nt.needsLights&&Et(Ge,$s),mt&&H.fog===!0&&J.refreshFogUniforms(Ge,mt),J.refreshMaterialUniforms(Ge,H,it,q,E.state.transmissionRenderTarget[y.id]),Nt.needsLights&&Nt.lightProbeGrid){let Le=Nt.lightProbeGrid;Ge.probesSH.value=Le.texture,Ge.probesMin.value.copy(Le.boundingBox.min),Ge.probesMax.value.copy(Le.boundingBox.max),Ge.probesResolution.value.copy(Le.resolution)}Lr.upload(W,Z(Nt),Ge,ot)}if(H.isShaderMaterial&&H.uniformsNeedUpdate===!0&&(Lr.upload(W,Z(Nt),Ge,ot),H.uniformsNeedUpdate=!1),H.isSpriteMaterial&&Ce.setValue(W,"center",$.center),Ce.setValue(W,"modelViewMatrix",$.modelViewMatrix),Ce.setValue(W,"normalMatrix",$.normalMatrix),Ce.setValue(W,"modelMatrix",$.matrixWorld),H.uniformsGroups!==void 0){let Le=H.uniformsGroups;for(let Qi=0,Ks=Le.length;Qi<Ks;Qi++){let Bh=Le[Qi];ut.update(Bh,kn),ut.bind(Bh,kn)}}return kn}function Et(y,D){y.ambientLightColor.needsUpdate=D,y.lightProbe.needsUpdate=D,y.sunLights.needsUpdate=D,y.sunLightShadows.needsUpdate=D,y.directionalLights.needsUpdate=D,y.directionalLightShadows.needsUpdate=D,y.pointLights.needsUpdate=D,y.pointLightShadows.needsUpdate=D,y.spotLights.needsUpdate=D,y.spotLightShadows.needsUpdate=D,y.rectAreaLights.needsUpdate=D,y.hemisphereLights.needsUpdate=D}function It(y){return y.isMeshLambertMaterial||y.isMeshToonMaterial||y.isMeshPhongMaterial||y.isMeshStandardMaterial||y.isShadowMaterial||y.isShaderMaterial&&y.lights===!0}this.getActiveCubeFace=function(){return V},this.getActiveMipmapLevel=function(){return z},this.getRenderTarget=function(){return X},this.setRenderTargetTextures=function(y,D,k){let H=j.get(y);H.__autoAllocateDepthBuffer=y.resolveDepthBuffer===!1,H.__autoAllocateDepthBuffer===!1&&(H.__useRenderToTexture=!1),j.get(y.texture).__webglTexture=D,j.get(y.depthTexture).__webglTexture=H.__autoAllocateDepthBuffer?void 0:k,H.__hasExternalTextures=!0},this.setRenderTargetFramebuffer=function(y,D){let k=j.get(y);k.__webglFramebuffer=D,k.__useDefaultFramebuffer=D===void 0},this.setRenderTarget=function(y,D=0,k=0){X=y,V=D,z=k;let H=null,$=!1,mt=!1;if(y){let wt=j.get(y);if(wt.__useDefaultFramebuffer!==void 0){x.bindFramebuffer(W.FRAMEBUFFER,wt.__webglFramebuffer),tt.copy(y.viewport),et.copy(y.scissor),dt=y.scissorTest,x.viewport(tt),x.scissor(et),x.setScissorTest(dt),G=-1;return}else if(wt.__webglFramebuffer===void 0)ot.setupRenderTarget(y);else if(wt.__hasExternalTextures)ot.rebindTextures(y,j.get(y.texture).__webglTexture,j.get(y.depthTexture).__webglTexture);else if(y.depthBuffer){let Jt=y.depthTexture;if(wt.__boundDepthTexture!==Jt){if(Jt!==null&&j.has(Jt)&&(y.width!==Jt.image.width||y.height!==Jt.image.height))throw new Error("THREE.WebGLRenderer: Attached DepthTexture is initialized to the incorrect size.");ot.setupDepthRenderbuffer(y)}}let Ot=y.texture;(Ot.isData3DTexture||Ot.isDataArrayTexture||Ot.isCompressedArrayTexture)&&(mt=!0);let Vt=j.get(y).__webglFramebuffer;y.isWebGLCubeRenderTarget?(Array.isArray(Vt[D])?H=Vt[D][k]:H=Vt[D],$=!0):y.samples>0&&ot.useMultisampledRTT(y)===!1?H=j.get(y).__webglMultisampledFramebuffer:Array.isArray(Vt)?H=Vt[k]:H=Vt,tt.copy(y.viewport),et.copy(y.scissor),dt=y.scissorTest}else tt.copy(Rt).multiplyScalar(it).floor(),et.copy(Yt).multiplyScalar(it).floor(),dt=Me;if(k!==0&&(H=B),x.bindFramebuffer(W.FRAMEBUFFER,H)&&x.drawBuffers(y,H),x.viewport(tt),x.scissor(et),x.setScissorTest(dt),$){let wt=j.get(y.texture);W.framebufferTexture2D(W.FRAMEBUFFER,W.COLOR_ATTACHMENT0,W.TEXTURE_CUBE_MAP_POSITIVE_X+D,wt.__webglTexture,k)}else if(mt){let wt=D;for(let Ot=0;Ot<y.textures.length;Ot++){let Vt=j.get(y.textures[Ot]);W.framebufferTextureLayer(W.FRAMEBUFFER,W.COLOR_ATTACHMENT0+Ot,Vt.__webglTexture,k,wt)}}else if(y!==null&&k!==0){let wt=j.get(y.texture);W.framebufferTexture2D(W.FRAMEBUFFER,W.COLOR_ATTACHMENT0,W.TEXTURE_2D,wt.__webglTexture,k)}G=-1};function Ut(y){let D=j.get(y);return(D.__readFormat!==y.format||D.__readType!==y.type)&&(D.__readFormat=y.format,D.__readType=y.type,D.__formatReadable=C.textureFormatReadable(y.format),D.__typeReadable=C.textureTypeReadable(y.type)),D}this.readRenderTargetPixels=function(y,D,k,H,$,mt,Ct,wt=0){if(!(y&&y.isWebGLRenderTarget)){$t("WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");return}let Ot=j.get(y).__webglFramebuffer;if(y.isWebGLCubeRenderTarget&&Ct!==void 0&&(Ot=Ot[Ct]),Ot){x.bindFramebuffer(W.FRAMEBUFFER,Ot);try{let Vt=y.textures[wt],Jt=Vt.format,se=Vt.type;y.textures.length>1&&W.readBuffer(W.COLOR_ATTACHMENT0+wt);let Bt=Ut(Vt);if(Bt.__formatReadable===!1){$t("WebGLRenderer.readRenderTargetPixels: renderTarget is not in RGBA or implementation defined format.");return}if(Bt.__typeReadable===!1){$t("WebGLRenderer.readRenderTargetPixels: renderTarget is not in UnsignedByteType or implementation defined type.");return}D>=0&&D<=y.width-H&&k>=0&&k<=y.height-$&&W.readPixels(D,k,H,$,_t.convert(Jt),_t.convert(se),mt)}finally{let Vt=X!==null?j.get(X).__webglFramebuffer:null;x.bindFramebuffer(W.FRAMEBUFFER,Vt)}}},this.readRenderTargetPixelsAsync=async function(y,D,k,H,$,mt,Ct,wt=0){if(!(y&&y.isWebGLRenderTarget))throw new Error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");let Ot=j.get(y).__webglFramebuffer;if(y.isWebGLCubeRenderTarget&&Ct!==void 0&&(Ot=Ot[Ct]),Ot)if(D>=0&&D<=y.width-H&&k>=0&&k<=y.height-$){x.bindFramebuffer(W.FRAMEBUFFER,Ot);let Vt=y.textures[wt],Jt=Vt.format,se=Vt.type;y.textures.length>1&&W.readBuffer(W.COLOR_ATTACHMENT0+wt);let Bt=Ut(Vt);if(Bt.__formatReadable===!1)throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in RGBA or implementation defined format.");if(Bt.__typeReadable===!1)throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in UnsignedByteType or implementation defined type.");let ve=W.createBuffer();W.bindBuffer(W.PIXEL_PACK_BUFFER,ve),W.bufferData(W.PIXEL_PACK_BUFFER,mt.byteLength,W.STREAM_READ),W.readPixels(D,k,H,$,_t.convert(Jt),_t.convert(se),0),W.bindBuffer(W.PIXEL_PACK_BUFFER,null);let Ie=X!==null?j.get(X).__webglFramebuffer:null;x.bindFramebuffer(W.FRAMEBUFFER,Ie);let Ft=W.fenceSync(W.SYNC_GPU_COMMANDS_COMPLETE,0);return W.flush(),await Zu(W,Ft,4),W.bindBuffer(W.PIXEL_PACK_BUFFER,ve),W.getBufferSubData(W.PIXEL_PACK_BUFFER,0,mt),W.bindBuffer(W.PIXEL_PACK_BUFFER,null),W.deleteBuffer(ve),W.deleteSync(Ft),mt}else throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: requested read bounds are out of range.")},this.copyFramebufferToTexture=function(y,D=null,k=0){let H=Math.pow(2,-k),$=Math.floor(y.image.width*H),mt=Math.floor(y.image.height*H),Ct=D!==null?D.x:0,wt=D!==null?D.y:0;ot.setTexture2D(y,0),W.copyTexSubImage2D(W.TEXTURE_2D,k,0,0,Ct,wt,$,mt),x.unbindTexture()},this.copyTextureToTexture=function(y,D,k=null,H=null,$=0,mt=0){let Ct,wt,Ot,Vt,Jt,se,Bt,ve,Ie,Ft=y.isCompressedTexture?y.mipmaps[mt]:y.image;if(k!==null)Ct=k.max.x-k.min.x,wt=k.max.y-k.min.y,Ot=k.isBox3?k.max.z-k.min.z:1,Vt=k.min.x,Jt=k.min.y,se=k.isBox3?k.min.z:0;else{let Ge=Math.pow(2,-$);Ct=Math.floor(Ft.width*Ge),wt=Math.floor(Ft.height*Ge),y.isDataArrayTexture?Ot=Ft.depth:y.isData3DTexture?Ot=Math.floor(Ft.depth*Ge):Ot=1,Vt=0,Jt=0,se=0}H!==null?(Bt=H.x,ve=H.y,Ie=H.z):(Bt=0,ve=0,Ie=0);let pe=_t.convert(D.format),ke=_t.convert(D.type),Nt;D.isData3DTexture?(ot.setTexture3D(D,0),Nt=W.TEXTURE_3D):D.isDataArrayTexture||D.isCompressedArrayTexture?(ot.setTexture2DArray(D,0),Nt=W.TEXTURE_2D_ARRAY):(ot.setTexture2D(D,0),Nt=W.TEXTURE_2D),x.activeTexture(W.TEXTURE0),x.pixelStorei(W.UNPACK_FLIP_Y_WEBGL,D.flipY),x.pixelStorei(W.UNPACK_PREMULTIPLY_ALPHA_WEBGL,D.premultiplyAlpha),x.pixelStorei(W.UNPACK_ALIGNMENT,D.unpackAlignment);let je=x.getParameter(W.UNPACK_ROW_LENGTH),ce=x.getParameter(W.UNPACK_IMAGE_HEIGHT),kn=x.getParameter(W.UNPACK_SKIP_PIXELS),fi=x.getParameter(W.UNPACK_SKIP_ROWS),Ji=x.getParameter(W.UNPACK_SKIP_IMAGES);x.pixelStorei(W.UNPACK_ROW_LENGTH,Ft.width),x.pixelStorei(W.UNPACK_IMAGE_HEIGHT,Ft.height),x.pixelStorei(W.UNPACK_SKIP_PIXELS,Vt),x.pixelStorei(W.UNPACK_SKIP_ROWS,Jt),x.pixelStorei(W.UNPACK_SKIP_IMAGES,se);let $s=y.isDataArrayTexture||y.isData3DTexture,Ce=D.isDataArrayTexture||D.isData3DTexture;if(y.isDepthTexture){let Ge=j.get(y),ji=j.get(D),Le=j.get(Ge.__renderTarget),Qi=j.get(ji.__renderTarget);x.bindFramebuffer(W.READ_FRAMEBUFFER,Le.__webglFramebuffer),x.bindFramebuffer(W.DRAW_FRAMEBUFFER,Qi.__webglFramebuffer);for(let Ks=0;Ks<Ot;Ks++)$s&&(W.framebufferTextureLayer(W.READ_FRAMEBUFFER,W.COLOR_ATTACHMENT0,j.get(y).__webglTexture,$,se+Ks),W.framebufferTextureLayer(W.DRAW_FRAMEBUFFER,W.COLOR_ATTACHMENT0,j.get(D).__webglTexture,mt,Ie+Ks)),W.blitFramebuffer(Vt,Jt,Ct,wt,Bt,ve,Ct,wt,W.DEPTH_BUFFER_BIT,W.NEAREST);x.bindFramebuffer(W.READ_FRAMEBUFFER,null),x.bindFramebuffer(W.DRAW_FRAMEBUFFER,null)}else if($!==0||y.isRenderTargetTexture||j.has(y)){let Ge=j.get(y),ji=j.get(D);x.bindFramebuffer(W.READ_FRAMEBUFFER,F),x.bindFramebuffer(W.DRAW_FRAMEBUFFER,P);for(let Le=0;Le<Ot;Le++)$s?W.framebufferTextureLayer(W.READ_FRAMEBUFFER,W.COLOR_ATTACHMENT0,Ge.__webglTexture,$,se+Le):W.framebufferTexture2D(W.READ_FRAMEBUFFER,W.COLOR_ATTACHMENT0,W.TEXTURE_2D,Ge.__webglTexture,$),Ce?W.framebufferTextureLayer(W.DRAW_FRAMEBUFFER,W.COLOR_ATTACHMENT0,ji.__webglTexture,mt,Ie+Le):W.framebufferTexture2D(W.DRAW_FRAMEBUFFER,W.COLOR_ATTACHMENT0,W.TEXTURE_2D,ji.__webglTexture,mt),$!==0?W.blitFramebuffer(Vt,Jt,Ct,wt,Bt,ve,Ct,wt,W.COLOR_BUFFER_BIT,W.NEAREST):Ce?W.copyTexSubImage3D(Nt,mt,Bt,ve,Ie+Le,Vt,Jt,Ct,wt):W.copyTexSubImage2D(Nt,mt,Bt,ve,Vt,Jt,Ct,wt);x.bindFramebuffer(W.READ_FRAMEBUFFER,null),x.bindFramebuffer(W.DRAW_FRAMEBUFFER,null)}else Ce?y.isDataTexture||y.isData3DTexture?W.texSubImage3D(Nt,mt,Bt,ve,Ie,Ct,wt,Ot,pe,ke,Ft.data):D.isCompressedArrayTexture?W.compressedTexSubImage3D(Nt,mt,Bt,ve,Ie,Ct,wt,Ot,pe,Ft.data):W.texSubImage3D(Nt,mt,Bt,ve,Ie,Ct,wt,Ot,pe,ke,Ft):y.isDataTexture?W.texSubImage2D(W.TEXTURE_2D,mt,Bt,ve,Ct,wt,pe,ke,Ft.data):y.isCompressedTexture?W.compressedTexSubImage2D(W.TEXTURE_2D,mt,Bt,ve,Ft.width,Ft.height,pe,Ft.data):W.texSubImage2D(W.TEXTURE_2D,mt,Bt,ve,Ct,wt,pe,ke,Ft);x.pixelStorei(W.UNPACK_ROW_LENGTH,je),x.pixelStorei(W.UNPACK_IMAGE_HEIGHT,ce),x.pixelStorei(W.UNPACK_SKIP_PIXELS,kn),x.pixelStorei(W.UNPACK_SKIP_ROWS,fi),x.pixelStorei(W.UNPACK_SKIP_IMAGES,Ji),mt===0&&D.generateMipmaps&&W.generateMipmap(Nt),x.unbindTexture()},this.initRenderTarget=function(y){j.get(y).__webglFramebuffer===void 0&&ot.setupRenderTarget(y)},this.initTexture=function(y){y.isCubeTexture?ot.setTextureCube(y,0):y.isData3DTexture?ot.setTexture3D(y,0):y.isDataArrayTexture||y.isCompressedArrayTexture?ot.setTexture2DArray(y,0):ot.setTexture2D(y,0),x.unbindTexture()},this.resetState=function(){V=0,z=0,X=null,x.reset(),Mt.reset()},typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}get coordinateSystem(){return ni}get outputColorSpace(){return this._outputColorSpace}set outputColorSpace(t){this._outputColorSpace=t;let e=this.getContext();e.drawingBufferColorSpace=me._getDrawingBufferColorSpace(t),e.unpackColorSpace=me._getUnpackColorSpace()}};var Ia=new O;function Wn(i,t,e,n,s,r){let a=2*Math.PI*s/4,o=Math.max(r-2*s,0),l=Math.PI/4;Ia.copy(t),Ia[n]=0,Ia.normalize();let c=.5*a/(a+o),h=1-Ia.angleTo(i)/l;return Math.sign(Ia[e])===1?h*c:o/(a+o)+c+c*(1-h)}var zl=class i extends de{constructor(t=1,e=1,n=1,s=2,r=.1){let a=s*2+1;if(r=Math.min(t/2,e/2,n/2,r),super(1,1,1,a,a,a),this.type="RoundedBoxGeometry",this.parameters={width:t,height:e,depth:n,segments:s,radius:r},a===1)return;let o=this.toNonIndexed();this.index=null,this.attributes.position=o.attributes.position,this.attributes.normal=o.attributes.normal,this.attributes.uv=o.attributes.uv;let l=new O,c=new O,h=new O(t,e,n).divideScalar(2).subScalar(r),p=this.attributes.position.array,d=this.attributes.normal.array,f=this.attributes.uv.array,_=p.length/6,b=new O,m=.5/a;for(let u=0,S=0;u<p.length;u+=3,S+=2)switch(l.fromArray(p,u),c.copy(l),c.x-=Math.sign(c.x)*m,c.y-=Math.sign(c.y)*m,c.z-=Math.sign(c.z)*m,c.normalize(),p[u+0]=h.x*Math.sign(l.x)+c.x*r,p[u+1]=h.y*Math.sign(l.y)+c.y*r,p[u+2]=h.z*Math.sign(l.z)+c.z*r,d[u+0]=c.x,d[u+1]=c.y,d[u+2]=c.z,Math.floor(u/_)){case 0:b.set(1,0,0),f[S+0]=Wn(b,c,"z","y",r,n),f[S+1]=1-Wn(b,c,"y","z",r,e);break;case 1:b.set(-1,0,0),f[S+0]=1-Wn(b,c,"z","y",r,n),f[S+1]=1-Wn(b,c,"y","z",r,e);break;case 2:b.set(0,1,0),f[S+0]=1-Wn(b,c,"x","z",r,t),f[S+1]=Wn(b,c,"z","x",r,n);break;case 3:b.set(0,-1,0),f[S+0]=1-Wn(b,c,"x","z",r,t),f[S+1]=1-Wn(b,c,"z","x",r,n);break;case 4:b.set(0,0,1),f[S+0]=1-Wn(b,c,"x","y",r,t),f[S+1]=1-Wn(b,c,"y","x",r,e);break;case 5:b.set(0,0,-1),f[S+0]=Wn(b,c,"x","y",r,t),f[S+1]=1-Wn(b,c,"y","x",r,e);break}}static fromJSON(t){return new i(t.width,t.height,t.depth,t.segments,t.radius)}};function Cd(i,t=!1){let e=i[0].index!==null,n=new Set(Object.keys(i[0].attributes)),s=new Set(Object.keys(i[0].morphAttributes)),r={},a={},o=i[0].morphTargetsRelative,l=new fn,c=0;for(let h=0;h<i.length;++h){let p=i[h],d=0;if(e!==(p.index!==null))return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+". All geometries must have compatible attributes; make sure index attribute exists among all geometries, or in none of them."),null;for(let f in p.attributes){if(!n.has(f))return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+'. All geometries must have compatible attributes; make sure "'+f+'" attribute exists among all geometries, or in none of them.'),null;r[f]===void 0&&(r[f]=[]),r[f].push(p.attributes[f]),d++}if(d!==n.size)return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+". Make sure all geometries have the same number of attributes."),null;if(o!==p.morphTargetsRelative)return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+". .morphTargetsRelative must be consistent throughout all geometries."),null;for(let f in p.morphAttributes){if(!s.has(f))return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+".  .morphAttributes must be consistent throughout all geometries."),null;a[f]===void 0&&(a[f]=[]),a[f].push(p.morphAttributes[f])}if(t){let f;if(e)f=p.index.count;else if(p.attributes.position!==void 0)f=p.attributes.position.count;else return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed with geometry at index "+h+". The geometry must have either an index or a position attribute"),null;l.addGroup(c,f,h),c+=f}}if(e){let h=0,p=[];for(let d=0;d<i.length;++d){let f=i[d].index;for(let _=0;_<f.count;++_)p.push(f.getX(_)+h);h+=i[d].attributes.position.count}l.setIndex(p)}for(let h in r){let p=Rd(r[h]);if(!p)return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed while trying to merge the "+h+" attribute."),null;l.setAttribute(h,p)}for(let h in a){let p=a[h][0].length;if(p!==0){l.morphAttributes=l.morphAttributes||{},l.morphAttributes[h]=[];for(let d=0;d<p;++d){let f=[];for(let b=0;b<a[h].length;++b)f.push(a[h][b][d]);let _=Rd(f);if(!_)return console.error("THREE.BufferGeometryUtils: .mergeGeometries() failed while trying to merge the "+h+" morphAttribute."),null;l.morphAttributes[h].push(_)}}}return l}function Rd(i){let t,e,n,s=-1,r=0;for(let c=0;c<i.length;++c){let h=i[c];if(t===void 0&&(t=h.array.constructor),t!==h.array.constructor)return console.error("THREE.BufferGeometryUtils: .mergeAttributes() failed. BufferAttribute.array must be of consistent array types across matching attributes."),null;if(e===void 0&&(e=h.itemSize),e!==h.itemSize)return console.error("THREE.BufferGeometryUtils: .mergeAttributes() failed. BufferAttribute.itemSize must be consistent across matching attributes."),null;if(n===void 0&&(n=h.normalized),n!==h.normalized)return console.error("THREE.BufferGeometryUtils: .mergeAttributes() failed. BufferAttribute.normalized must be consistent across matching attributes."),null;if(s===-1&&(s=h.gpuType),s!==h.gpuType)return console.error("THREE.BufferGeometryUtils: .mergeAttributes() failed. BufferAttribute.gpuType must be consistent across matching attributes."),null;r+=h.count*e}let a=new t(r),o=new on(a,e,n),l=0;for(let c=0;c<i.length;++c){let h=i[c];if(h.isInterleavedBufferAttribute){let p=l/e;for(let d=0,f=h.count;d<f;d++)for(let _=0;_<e;_++){let b=h.getComponent(d,_);o.setComponent(d+p,_,b)}}else a.set(h.array,l);l+=h.count*e}return s!==void 0&&(o.gpuType=s),o}function Ul(){return{matte:new Ae({vertexColors:!0,roughness:.84,metalness:0}),satin:new Ae({vertexColors:!0,roughness:.42,metalness:.05}),metal:new Ae({vertexColors:!0,roughness:.38,metalness:.55}),glass:new Ae({vertexColors:!0,roughness:.08,metalness:.1,transparent:!0,opacity:.55,depthWrite:!1}),glow:new Te({vertexColors:!0,toneMapped:!1})}}function Fl(i){for(let t of Object.values(i))t.dispose()}var Pd=new Map;function Nr(i,t){let e=Pd.get(i);return e||(e=t(),Pd.set(i,e)),e}var a_=.02;function L(i,t,e,n=0){let s=Math.min(n,i/2,t/2,e/2);return Nr(`box:${i}:${t}:${e}:${s}`,()=>s>=a_?new zl(i,t,e,1,s):new de(i,t,e))}function Ht(i,t,e,n=16){return Nr(`cyl:${i}:${t}:${e}:${n}`,()=>new Mr(i,t,e,n))}function Xn(i,t=12,e=8){return Nr(`sph:${i}:${t}:${e}`,()=>new pa(i,t,e))}function Xi(i,t,e=8){return Nr(`cone:${i}:${t}:${e}`,()=>new da(i,t,e))}function cn(i,t,e=Math.PI*2,n=8,s=24){return Nr(`torus:${i}:${t}:${e}:${n}:${s}`,()=>new ma(i,t,n,s,e))}function qn(i){return Nr(`dodeca:${i}`,()=>new fa(i,0))}var o_=new be,Id=new Xe,l_=new zn,Ld=new O,Dd=new O,Nl=new jt;function c_(i,t,e){let n=i.index?i.toNonIndexed():i.clone();n.deleteAttribute("uv"),Ld.set(t.x??0,t.y??0,t.z??0),Id.setFromEuler(l_.set(t.rx??0,t.ry??0,t.rz??0)),Dd.set(t.sx??1,t.sy??1,t.sz??1),n.applyMatrix4(o_.compose(Ld,Id,Dd)),Nl.set(e);let s=n.getAttribute("position").count,r=new Float32Array(s*3);for(let a=0;a<s;a+=1)r[a*3]=Nl.r,r[a*3+1]=Nl.g,r[a*3+2]=Nl.b;return n.setAttribute("color",new on(r,3)),n}var ie=class{constructor(){re(this,"groups",new Map)}add(t,e,n={},s="matte",r=!0){let a=`${s}|${r?1:0}`,o=this.groups.get(a);o||(o=[],this.groups.set(a,o)),o.push(c_(t,n,e))}build(){let t=[];for(let[e,n]of this.groups){let[s,r]=e.split("|"),a=Cd(n,!1);for(let o of n)o.dispose();a&&(a.computeBoundingSphere(),t.push({geometry:a,finish:s,shadow:r==="1"}))}return this.groups.clear(),t}};function Ei(i,t,e=!0){return i.map(({geometry:n,finish:s,shadow:r})=>{let a=new Xt(n,t[s]);return a.castShadow=r&&s!=="glass"&&s!=="glow",a.receiveShadow=e&&s!=="glow",a.matrixAutoUpdate=!1,a.updateMatrix(),a})}var Wt={x0:-6,x1:6,z0:-4.5,z1:4.5},La=2.6,Yn=.18;function Fn(i){return i?{wall:"#4d5466",wallLow:"#434a5b",trim:"#262a33",skirt:"#2b2f38",sky:"#1d2e5c",frame:"#2c303a",wood:"#4e3b2c",woodLight:"#5f4836",deskTop:"#6b5a4a",deskFrame:"#3a3f4b",chair:"#2f3442",seat:"#3d4456",pot:"#8a5a44",soil:"#3a2a20",leaf:"#4f8a5b",leafLight:"#6aa86f",metal:"#5d6470",dim:"#203048"}:{wall:"#f1ece4",wallLow:"#e6ddd0",trim:"#d9cfc1",skirt:"#e9e4dc",sky:"#bfe3ff",frame:"#e8e2d8",wood:"#a5784f",woodLight:"#bf9468",deskTop:"#e8dccb",deskFrame:"#9aa1ab",chair:"#4c5566",seat:"#5c677c",pot:"#c1785a",soil:"#5a4030",leaf:"#4f8a5b",leafLight:"#6aa86f",metal:"#9aa1ab",dim:"#203048"}}function Da(i,t){let e=document.createElement("canvas");e.width=i,e.height=i,t(e.getContext("2d"));let n=new Hi(e);return n.wrapS=gi,n.wrapT=gi,n.colorSpace=He,n.anisotropy=4,n}function h_(i,t){if(i==="wood")return Da(512,n=>{n.fillStyle=t?"#76604b":"#c9a37c",n.fillRect(0,0,512,512);for(let s=0;s<8;s+=1){let r=s%2*128;for(let a=-1;a<3;a+=1){let o=(s*7+a*3)%5/5;n.fillStyle=t?`rgba(0,0,0,${.08+o*.08})`:`rgba(90,55,25,${.05+o*.07})`,n.fillRect(a*256+r+2,s*64+2,252,60)}}});if(i==="raised")return Da(512,n=>{n.fillStyle=t?"#5a606c":"#c9ced6",n.fillRect(0,0,512,512);for(let s=0;s<4;s+=1)for(let r=0;r<4;r+=1)if(n.fillStyle=t?"#646b78":"#d6dbe2",n.fillRect(r*128+3,s*128+3,122,122),(s+r)%3===0){n.fillStyle=t?"#3e434d":"#9aa1ab";for(let a=0;a<8;a+=1)for(let o=0;o<8;o+=1)n.fillRect(r*128+14+o*13,s*128+14+a*13,5,5)}});if(i==="tile"||i==="stone")return Da(512,n=>{n.fillStyle=i==="stone"?t?"#6d6a66":"#e4ded4":t?"#5d6470":"#dfe2e6",n.fillRect(0,0,512,512);let s=i==="stone"?256:128;for(let r=0;r<512/s;r+=1)for(let a=0;a<512/s;a+=1){let o=(r*5+a*3)%4/4;n.fillStyle=t?`rgba(255,255,255,${.02+o*.03})`:`rgba(0,0,0,${.02+o*.03})`,n.fillRect(a*s+2,r*s+2,s-4,s-4),i==="stone"&&(n.strokeStyle=t?"rgba(255,255,255,0.05)":"rgba(120,110,95,0.12)",n.beginPath(),n.moveTo(a*s+s*.2,r*s+s*(.3+o*.4)),n.bezierCurveTo(a*s+s*.5,r*s+s*.1,a*s+s*.6,r*s+s*.9,a*s+s*.9,r*s+s*.6),n.stroke())}});if(i==="carpet")return Da(256,n=>{n.fillStyle=t?"#3c4456":"#c8cfdb",n.fillRect(0,0,256,256);for(let s=0;s<900;s+=1)n.fillStyle=t?"rgba(255,255,255,0.03)":"rgba(0,0,0,0.04)",n.fillRect(s*97%256,s*61%256,2,2)});let e=i==="lawn";return Da(256,n=>{n.fillStyle=e?t?"#2f4a3a":"#9cc49a":t?"#5a4a3a":"#c8b08a",n.fillRect(0,0,256,256);for(let s=0;s<700;s+=1){let r=s*13%3===0;n.fillStyle=r?t?"rgba(255,255,255,0.05)":"rgba(255,255,255,0.18)":t?"rgba(0,0,0,0.12)":"rgba(80,60,30,0.1)",n.fillRect(s*89%256,s*47%256,2+s%3,2)}})}function wi(i,t,e,n=4){let s=e.x1-e.x0,r=e.z1-e.z0,a=h_(i,t);a.repeat.set(s/n,r/n);let o=new de(s,.24,r);o.translate((e.x0+e.x1)/2,-.12,(e.z0+e.z1)/2);let l=new Ae({map:a,roughness:i==="stone"||i==="tile"?.55:.85}),c=new Xt(o,l);return c.receiveShadow=!0,c.matrixAutoUpdate=!1,{mesh:c,dispose(){o.dispose(),l.dispose(),a.dispose()}}}function Ur(i,t,e={},n){let s=Fn(t),r=Wt,a=r.x1-r.x0,o=r.z1-r.z0,l=e.wall??s.wall,c=e.low??s.wallLow,h=.95;i.add(L(a+.1,.12,o+.1),s.skirt,{y:-.3},"matte",!1),i.add(L(a,h,Yn+.02),c,{y:h/2,z:r.z0-Yn/2}),i.add(L(a,La-h,Yn),l,{y:h+(La-h)/2,z:r.z0-Yn/2}),i.add(L(Yn+.02,h,o+Yn),c,{x:r.x0-Yn/2,y:h/2,z:-Yn/2}),i.add(L(Yn,La-h,o+Yn),l,{x:r.x0-Yn/2,y:h+(La-h)/2,z:-Yn/2});for(let[p,d]of[[.06,.12],[h,.04],[La-.02,.05]])i.add(L(a,d,.04),s.trim,{y:p,z:r.z0+.02},"satin",!1),i.add(L(.04,d,o),s.trim,{x:r.x0+.02,y:p},"satin",!1);if(n){i.add(L(n.width+.2,1.36,.06,.02),s.frame,{x:n.x,y:1.62,z:r.z0+.03},"satin",!1),i.add(L(n.width,1.14,.02),s.sky,{x:n.x,y:1.62,z:r.z0+.065},"glow",!1);let p=Math.max(2,Math.round(n.width/1.1));for(let d=1;d<p;d+=1)i.add(L(.06,1.16,.05),s.frame,{x:n.x-n.width/2+n.width/p*d,y:1.62,z:r.z0+.08},"satin",!1);i.add(L(n.width+.3,.05,.16,.015),s.trim,{x:n.x,y:.92,z:r.z0+.08},"satin",!1)}}function qi(i,t,e,n,s=!1){let r=Fn(t);i.add(Ht(.21,.15,.38,18),r.pot,{x:e,y:.19,z:n},"satin"),i.add(cn(.205,.02,Math.PI*2,6,18),r.pot,{x:e,y:.38,z:n,rx:Math.PI/2},"satin",!1),i.add(Ht(.19,.19,.02,16),r.soil,{x:e,y:.36,z:n},"matte",!1),s&&i.add(Ht(.02,.025,.7,6),"#5b4636",{x:e,y:.7,z:n},"matte");let a=s?1.05:.58;for(let[o,l,c,h,p]of[[0,0,0,.3,!1],[.14,.12,.05,.2,!0],[-.12,.16,-.06,.18,!0],[.02,.3,.02,.17,!1]])i.add(qn(h*(s?.9:1)),p?r.leafLight:r.leaf,{x:e+o,y:a+l,z:n+c,ry:o*7},"matte")}function Ol(i,t,e,n,s=1.2){let r=Fn(t),a=.7,o=n-.75;i.add(L(s,.045,a,.015),r.deskTop,{x:e,y:.645,z:n},"satin");for(let l of[-1,1])i.add(L(.04,.62,a-.06,.01),r.deskFrame,{x:e+l*(s/2-.05),y:.31,z:n},"metal");return i.add(L(.22,.014,.14,.006),"#2a2d35",{x:e,y:.674,z:n+.2},"metal"),i.add(L(.04,.2,.03),"#5d6470",{x:e,y:.77,z:n+.22},"metal"),i.add(L(.64,.4,.035,.014),"#1d2027",{x:e,y:1,z:n+.2},"satin"),i.add(L(.38,.018,.13,.006),"#2a2d35",{x:e,y:.676,z:n-.12},"satin"),i.add(L(.46,.07,.44,.03),r.seat,{x:e,y:.29,z:o},"matte"),i.add(L(.44,.46,.06,.03),r.chair,{x:e,y:.62,z:o-.23,rx:-.08},"matte"),i.add(Ht(.025,.025,.2,10),"#5d6470",{x:e,y:.16,z:o},"metal"),i.add(Ht(.2,.22,.03,12),"#3a3f4b",{x:e,y:.03,z:o},"metal",!1),new O(e,1,n+.18)}var XM=L(.58,.34,.008);function nn(i,t){let e=new ae;for(let n of Ei(i.build(),t))e.add(n);return e}function Mn(i){i.traverse(t=>{t instanceof Xt&&!t.userData.shared&&t.geometry.dispose()})}function vh(i,t=0){let e=2166136261^t;for(let n of i)e=Math.imul(e^n.codePointAt(0),16777619);return(e>>>0)%10007/10007}var u_={x0:-14,x1:14,z0:-10,z1:11},li={studio:{x:0,z:-5.5,top:0},library:{x:-9,z:-4.5,top:3.3},site:{x:9,z:-4.5,top:2.6},duty:{x:9,z:4.5,top:4.4},desk:{x:0,z:7.5,top:2.9}},Yi=1.15,zd=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Fn(r),o=wi("lawn",r,u_,6);t.add(o.mesh);let l=new ie,c=r?"#5d5a56":"#e4ded4";l.add(Ht(3.2,3.2,.04,40),c,{y:.02},"matte",!1);for(let T of Object.values(li)){let I=Math.hypot(T.x,T.z);l.add(L(1.1,.035,I),c,{x:T.x/2,y:.018,z:T.z/2,ry:Math.atan2(T.x,T.z)},"matte",!1)}l.add(Ht(.9,1,.3,24),r?"#6f6b66":"#cfc8bc",{y:.15},"satin"),l.add(Ht(.75,.75,.04,24),r?"#2d4f73":"#7fb6d6",{y:.3},"glass",!1);for(let[T,I]of[[-3.5,-2.5],[3.5,-2.5],[-3.5,3],[3.5,3]])l.add(Ht(.05,.07,2.5,8),a.metal,{x:T,y:1.25,z:I},"metal"),l.add(Xn(.16,10,8),"#ffe2a8",{x:T,y:2.6,z:I},r?"glow":"satin",!1);for(let[T,I,N]of[[-13,-8.5,1],[-5,-9,.8],[5,-9,.9],[13,-8.5,1],[-13,0,.9],[13,0,1],[-12.5,9.5,1],[-5,10,.8],[5,10,.9],[12.5,9.5,1],[-4.5,2.2,.7],[4.5,2.2,.7],[-10,3.6,1.1],[-7.8,5.4,.85],[-10.6,6.2,.9]])l.add(Ht(.08*N,.11*N,.9*N,8),"#5b4636",{x:T,y:.45*N,z:I},"matte"),l.add(qn(.6*N),a.leaf,{x:T,y:1.15*N,z:I},"matte"),l.add(qn(.42*N),a.leafLight,{x:T+.25*N,y:1.45*N,z:I-.1},"matte");let h=r?"#5a6274":"#efe9df",p=r?"#3a3f4b":"#b8b2a8",d=r?"#1d2e5c":"#9fc9e6";{let{x:T,z:I}=li.library;l.add(L(5.2,.3,3.6,.03),c,{x:T,y:.15,z:I},"matte"),l.add(L(4.6,2.2,2.8,.03),h,{x:T,y:1.4,z:I-.2},"satin");for(let N=0;N<6;N+=1)l.add(Ht(.13,.15,2.2,12),c,{x:T-2+N*.8,y:1.4,z:I+1.45},"satin");l.add(L(5,.25,3.3,.02),c,{x:T,y:2.62,z:I},"satin"),l.add(Xi(2.9,.75,4),p,{x:T,y:3.1,z:I,ry:Math.PI/4,sz:.62},"satin")}{let{x:T,z:I}=li.site;l.add(L(5,.03,4.2),r?"#5a4a3a":"#c8b08a",{x:T,y:.02,z:I},"matte",!1);for(let[N,B,F,P]of[[0,-2.1,5,.04],[0,2.1,5,.04],[-2.5,0,.04,4.2],[2.5,0,.04,4.2]])l.add(L(F,.8,P),r?"#3c4c5e":"#7d97b0",{x:T+N,y:.4,z:I+B},"glass",!1);for(let[N,B,F,P]of[[-1.5,-.8,1.2,"#5b7db1"],[-.7,-.9,.8,"#4f8a5b"],[-1.4,.6,.6,"#e3dccb"],[-.5,.5,1.5,"#5b7db1"],[.4,.9,.5,"#9aa1ab"]])l.add(L(.6,F,.6,.02),P,{x:T+N,y:F/2,z:I+B},"satin");l.add(L(.14,3.6,.14),"#e0a13a",{x:T+1.6,y:1.8,z:I-1.2},"metal"),l.add(L(4,.12,.14),"#e0a13a",{x:T+.4,y:3.6,z:I-1.2},"metal"),l.add(Ht(.01,.01,1.4,4),"#2a2d35",{x:T-1.2,y:2.9,z:I-1.2},"metal",!1)}{let{x:T,z:I}=li.duty;l.add(L(3.8,1.8,3,.04),h,{x:T,y:.9,z:I},"satin"),l.add(Xi(2.8,1,4),p,{x:T,y:2.3,z:I,ry:Math.PI/4,sz:.8},"satin"),l.add(L(1,3.6,1,.03),h,{x:T+1.2,y:1.8,z:I+.6},"satin"),l.add(Xi(.8,.8,4),p,{x:T+1.2,y:4,z:I+.6,ry:Math.PI/4},"satin"),l.add(Ht(.38,.38,.04,24),"#fbfaf7",{x:T+1.2,y:3,z:I+1.11,rx:Math.PI/2},"satin",!1),l.add(cn(.38,.03,Math.PI*2,6,24),"#3b3b40",{x:T+1.2,y:3,z:I+1.13},"metal",!1),l.add(L(.6,1.2,.04),a.wood,{x:T-.5,y:.6,z:I+1.51},"satin",!1)}{let{x:T,z:I}=li.desk;l.add(L(4,1.7,2.4,.04),h,{x:T,y:.85,z:I},"satin"),l.add(L(4.4,.14,2.8,.03),p,{x:T,y:1.77,z:I+.1},"satin"),l.add(L(1.6,1.3,.04),d,{x:T+.8,y:.75,z:I+1.21},"glass",!1),l.add(Ht(.04,.06,1.8,8),a.metal,{x:T-1.5,y:2.7,z:I},"metal")}l.add(L(4.8,.35,4.8,.04),c,{x:li.studio.x,y:.17,z:li.studio.z},"matte"),t.add(nn(l,e));let f=new ae;t.add(f);let _=new Map,b=(T,I)=>{let N=new Te({color:a.dim,toneMapped:!1});_.set(T,N);let B=new de(1,1,1);for(let[F,P,V,z,X,G]of I){let Y=new Xt(B,N);Y.position.set(F,P,V),Y.scale.set(z,X,G),t.add(Y)}},m=li;b("library",[[m.library.x-1.2,1.5,m.library.z+1.21,.7,1,.03],[m.library.x,1.5,m.library.z+1.21,.7,1,.03],[m.library.x+1.2,1.5,m.library.z+1.21,.7,1,.03]]),b("site",[[m.site.x+.4,3.75,m.site.z-1.2,.18,.18,.18]]),b("duty",[[m.duty.x-.5,1.2,m.duty.z+1.52,.9,.6,.03],[m.duty.x+.9,1,m.duty.z-1.52,.9,.6,.03]]),b("desk",[[m.desk.x-1,1,m.desk.z+1.22,1,.6,.03],[m.desk.x-1.5,3.65,m.desk.z,.12,.12,.12]]);let u=new Te({color:a.dim,toneMapped:!1});_.set("studio",u);let S=new Ae({color:"#25252a",roughness:.5}),R=new Xt(new de(.04,.22,.01).translate(0,.1,0),S),v=new Xt(new de(.03,.32,.01).translate(0,.15,0),S);R.position.set(m.duty.x+1.2,3,m.duty.z+1.16),v.position.set(m.duty.x+1.2,3,m.duty.z+1.17),t.add(R,v);let M=new Te({visible:!1});for(let[T,I]of Object.entries(li)){let N=new Xt(new de(5.2,T==="studio"?8:I.top+.4,4.2),M);N.position.set(I.x,(T==="studio"?8:I.top+.4)/2,I.z),t.add(N),i.pickable(N,`place:${T}`)}let E=0,A=null,g=T=>{if(T===E)return;E=T;for(let P of[...f.children])P.removeFromParent(),P instanceof Xt&&P.material===u?P.geometry.dispose():Mn(P);let I=new ie,{x:N,z:B}=m.studio;for(let P=0;P<T;P+=1){let V=.35+P*Yi;I.add(L(4,Yi-.08,4,.03),h,{x:N,y:V+Yi/2,z:B},"satin"),I.add(L(4.1,.08,4.1,.02),a.trim,{x:N,y:V+Yi-.04,z:B},"satin",!1)}I.add(L(4.3,.2,4.3,.03),p,{x:N,y:.35+T*Yi+.1,z:B},"satin"),I.add(Ht(.04,.05,1.2,8),a.metal,{x:N+1.5,y:.35+T*Yi+.8,z:B-1.5},"metal"),f.add(nn(I,e));let F=new de(1,1,1);for(let P=0;P<T;P+=1){let V=.35+P*Yi+Yi/2;for(let[z,X,G,Y]of[[N,B+2.01,3.4,.03],[N+2.01,B,.03,3.4]]){let tt=new Xt(F,u);tt.position.set(z,V,X),tt.scale.set(G,.45,Y),tt.userData.level=P,f.add(tt)}}};g(1);let w=T=>T==="studio"?.35+E*Yi+1:m[T].top+.5;return{frame:{min:{x:-12.5,y:0,z:-8.5},max:{x:12.5,y:4,z:9.5},polar:.95,azimuth:.55},lamps:[{x:-3.5,y:2.6,z:-2.5},{x:3.5,y:2.6,z:-2.5},{x:-3.5,y:2.6,z:3},{x:3.5,y:2.6,z:3}],update({model:T,t:I}){A=T,g(Math.max(1,Math.min(6,T.floors)));let N={};for(let B of Object.keys(li)){let F=T.spots[B];N[B]={at:{x:m[B].x,y:w(B),z:m[B].z},title:I(`places.${B}.title`),detail:F.detail,...F.alert?{tone:"alert"}:F.busy?{tone:"busy"}:{},pick:`place:${B}`}}return{people:[],labels:N}},tick(T){let I=new Date;v.rotation.z=-((I.getMinutes()+I.getSeconds()/60)/60)*Math.PI*2,R.rotation.z=-((I.getHours()%12+I.getMinutes()/60)/12)*Math.PI*2;for(let[N,B]of _){let F=A?.spots[N],P=s?1:.85+Math.sin(T*(N==="site"||N==="desk"?5:1.5))*.15;F?.alert?B.color.set("#f2b33d").multiplyScalar(P):F?.busy?B.color.set(r?"#ffd27a":"#ffcf6a").multiplyScalar(P):B.color.set(r?"#2a3550":"#7d8ea3")}return!1},target(T){let I=T.startsWith("place:")?T.slice(6):null;return!I||!(I in li)?null:{x:m[I].x,y:I==="studio"?1.6:1,z:m[I].z}},dispose(){o.dispose();for(let T of[...t.children])Mn(T);for(let T of _.values())T.dispose();S.dispose(),M.dispose()}}};var d_={lead:{shirt:"#2f5d9e",pants:"#2b3140",skin:"#f1c7a5",hair:"#2b211c",hairStyle:"short",accessory:"badge"},legal:{shirt:"#3e3f55",pants:"#22232c",skin:"#efc6a6",hair:"#1e1a18",hairStyle:"bun",accessory:"tie"},teacher:{shirt:"#8a8d3b",pants:"#3b3a30",skin:"#d39b78",hair:"#4a4a4a",hairStyle:"short",accessory:"glasses"}},Nd=["#3f88c5","#d1495b","#66a182","#edae49","#8f6593","#00798c","#e76f51"],Ud=["#2b211c","#6b3e26","#a0522d","#1b1b1b","#c19a6b"],Fd=["short","long","bun","spiky"],Od=["none","glasses","scarf","cap"];function f_(i){let t=2166136261;for(let e of i)t=Math.imul(t^e.codePointAt(0),16777619);return t>>>0}function Ti(i){let t=d_[i];if(t)return t;let e=f_(i);return{shirt:Nd[e%Nd.length],pants:"#30343e",skin:["#f1c7a5","#d8a483","#c99272","#e9b896"][(e>>3)%4],hair:Ud[(e>>5)%Ud.length],hairStyle:Fd[(e>>7)%Fd.length],accessory:Od[(e>>9)%Od.length]}}var At={x0:-6,x1:6,z0:-4.5,z1:4.5,height:2.6},Bl=[0,-1.8,1.8,-3.6,3.6],bh=Bl.length,Bd=-2.2,Zi={width:1.2,depth:.7},Ai=-2.95;function Fr(i){return{x:Bl[i%Bl.length],z:Bd}}function za(i){let{x:t}=Fr(i);return{x:t,z:Ai,face:{x:t,z:Bd+2},sit:!0}}var sn={x0:-6,x1:-5.6,z0:-2,z1:-.2},kd=[-1.6,-1.1,-.6].map(i=>({x:-5.15,z:i,face:{x:-7,z:i},sit:!1})),Zn={x:-5.92,z0:.4,z1:1.9},Hd={x:-5,z:1.15,face:{x:-7,z:1.15},sit:!1},rn={x0:5.25,x1:5.9,z0:-4.3,z1:-3.3},an={x0:5.35,x1:5.9,z0:-3.1,z1:-1.7},Vd=[{x:4.95,z:-2.05,face:{x:7,z:-2.05},sit:!1}],le={x:4.4,z:-2.4,door:{x0:4.55,x1:5.2}},Gd=[{x:4.95,z:-2.75,face:{x:7,z:-2.75},sit:!1},{x:4.75,z:-3.65,face:{x:7,z:-3.65},sit:!1}],Wd={x:4.85,z:-1.9,face:{x:3.2,z:1.5},sit:!1},Se={x:1.6,z:1.5,radius:.85},Or=Array.from({length:6},(i,t)=>{let e=t/6*Math.PI*2+Math.PI/6;return{x:Se.x+Math.cos(e)*1.4,z:Se.z+Math.sin(e)*1.4,face:{x:Se.x,z:Se.z},sit:!0}}),qe={x0:-5.75,x1:-5.05,z0:2.3,z1:4.1},p_=[2.8,3.6].map(i=>({x:-4.8,z:i,face:{x:0,z:i},sit:!0})),Rn={x0:-3.3,x1:-1.9,z0:3.95,z1:4.45},m_={x:-2.6,z:3.35,face:{x:-2.6,z:6},sit:!1},On={x:5.1,z:3.3},g_={x:4.5,z:3.3,face:{x:7,z:3.3},sit:!1},Mh=[{x:-5.5,z:-4},{x:5.45,z:4.05},{x:-.6,z:4.1},{x:4.05,z:-4.05}],kl=[-.9,.9].map(i=>({x:i,z:-3.85,face:{x:i,z:-7},sit:!1})),mn={x0:-5.1,x1:-4.4,z0:-4.4,z1:-3.85},Sh={x:-4.75,z:-3.25,face:{x:-4.75,z:-6},sit:!1},Ve={x:At.x1,z0:.6,z1:1.8},Br={x:At.x1+.9,z:(Ve.z0+Ve.z1)/2,face:{x:At.x1+4,z:(Ve.z0+Ve.z1)/2},sit:!1},Na=[m_,g_,...p_,kl[1]];function Xd(){let i=Bl.map((e,n)=>{let{x:s,z:r}=Fr(n);return{x0:s-Zi.width/2,x1:s+Zi.width/2,z0:r-Zi.depth/2,z1:r+Zi.depth/2}}),t=Mh.map(({x:e,z:n})=>({x0:e-.25,x1:e+.25,z0:n-.25,z1:n+.25}));return[...i,sn,rn,an,{x0:le.x-.04,x1:le.x+.04,z0:At.z0,z1:le.z},{x0:le.x-.04,x1:le.door.x0,z0:le.z-.04,z1:le.z+.04},{x0:Se.x-Se.radius,x1:Se.x+Se.radius,z0:Se.z-Se.radius,z1:Se.z+Se.radius},qe,Rn,mn,{x0:On.x-.2,x1:On.x+.2,z0:On.z-.2,z1:On.z+.2},...t]}var Gs=.2,Hl=.18,$n=class{constructor(t,e=At){re(this,"columns");re(this,"rows");re(this,"blocked");re(this,"bounds");this.bounds={x0:e.x0,x1:e.x1,z0:e.z0,z1:e.z1},this.columns=Math.round((e.x1-e.x0)/Gs),this.rows=Math.round((e.z1-e.z0)/Gs),this.blocked=new Uint8Array(this.columns*this.rows);for(let n=0;n<this.rows;n+=1)for(let s=0;s<this.columns;s+=1){let{x:r,z:a}=this.center(s,n),o=r<e.x0+.25||r>e.x1-.15||a<e.z0+.25||a>e.z1-.15,l=t.some(c=>r>c.x0-Hl&&r<c.x1+Hl&&a>c.z0-Hl&&a<c.z1+Hl);this.blocked[n*this.columns+s]=o||l?1:0}}center(t,e){return{x:this.bounds.x0+(t+.5)*Gs,z:this.bounds.z0+(e+.5)*Gs}}cell(t){let e=Math.min(this.columns-1,Math.max(0,Math.floor((t.x-this.bounds.x0)/Gs))),n=Math.min(this.rows-1,Math.max(0,Math.floor((t.z-this.bounds.z0)/Gs)));return[e,n]}isBlocked(t,e){return t<0||e<0||t>=this.columns||e>=this.rows?!0:this.blocked[e*this.columns+t]===1}nearestFree(t){let[e,n]=this.cell(t);if(!this.isBlocked(e,n))return[e,n];for(let s=1;s<12;s+=1){let r=null,a=1/0;for(let o=-s;o<=s;o+=1)for(let l=-s;l<=s;l+=1){if(Math.max(Math.abs(l),Math.abs(o))!==s||this.isBlocked(e+l,n+o))continue;let c=this.center(e+l,n+o),h=(c.x-t.x)**2+(c.z-t.z)**2;h<a&&(a=h,r=[e+l,n+o])}if(r)return r}return[e,n]}clear(t,e){let n=Math.ceil(Math.hypot(e.x-t.x,e.z-t.z)/(Gs/2));for(let s=1;s<n;s+=1){let r=s/n,[a,o]=this.cell({x:t.x+(e.x-t.x)*r,z:t.z+(e.z-t.z)*r});if(this.isBlocked(a,o))return!1}return!0}path(t,e){if(this.clear(t,e))return[e];let[n,s]=this.nearestFree(t),[r,a]=this.nearestFree(e),o=this.columns*this.rows,l=s*this.columns+n,c=a*this.columns+r,h=new Float32Array(o).fill(1/0),p=new Int32Array(o).fill(-1),d=new Uint8Array(o),f=[l],_=new Float32Array(o).fill(1/0),b=M=>{let E=Math.abs(M%this.columns-r),A=Math.abs(Math.floor(M/this.columns)-a);return Math.max(E,A)+(Math.SQRT2-1)*Math.min(E,A)};for(h[l]=0,_[l]=b(l);f.length>0;){let M=0;for(let w=1;w<f.length;w+=1)_[f[w]]<_[f[M]]&&(M=w);let E=f[M];if(f[M]=f[f.length-1],f.pop(),E===c)break;if(d[E])continue;d[E]=1;let A=E%this.columns,g=Math.floor(E/this.columns);for(let w=-1;w<=1;w+=1)for(let T=-1;T<=1;T+=1){if(!T&&!w)continue;let I=A+T,N=g+w;if(this.isBlocked(I,N)||T&&w&&(this.isBlocked(A+T,g)||this.isBlocked(A,g+w)))continue;let B=N*this.columns+I,F=h[E]+(T&&w?Math.SQRT2:1);F<h[B]&&(h[B]=F,p[B]=E,_[B]=F+b(B),f.push(B))}}if(p[c]===-1&&c!==l)return[e];let m=[];for(let M=c;M!==-1&&M!==l;M=p[M])m.push(this.center(M%this.columns,Math.floor(M/this.columns)));m.reverse();let u=[...m,e],S=[],R=t,v=0;for(;v<u.length;){let M=v;for(let E=u.length-1;E>v;E-=1)if(this.clear(R,u[E])){M=E;break}R=u[M],S.push(R),v=M+1}return S}};var ue={x:0,z:-2.3,width:3.4},Bn={x:-3.6,z:2.6},ys={z:-1,length:3.2},vs={x:4.6,z:4.4},Ws={x:ue.x,z:ue.z-.75,face:{x:ue.x,z:6},sit:!0},x_=i=>({x:ue.x-1+i*1,z:ue.z+.85,face:{x:ue.x-1+i*1,z:-9},sit:!1}),__=i=>({x:Bn.x-1.1+i*.75,z:Bn.z-.1,face:{x:Bn.x-1.1+i*.75,z:-9},sit:!0}),qd=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Fn(r),o=wi("stone",r,Wt,2.4);t.add(o.mesh);let l=new ie;Ur(l,r,{wall:r?"#4b5163":"#f3efe8",low:r?"#40465a":"#e5ddd0"},{x:3.2,width:3.2}),l.add(L(ue.width,1.05,.5,.04),a.wood,{x:ue.x,y:.525,z:ue.z+.1},"satin"),l.add(L(ue.width+.1,.05,.62,.015),a.deskTop,{x:ue.x,y:1.07,z:ue.z+.1},"satin"),l.add(L(ue.width-.2,.7,.04),a.woodLight,{x:ue.x,y:.45,z:ue.z+.37},"satin",!1),l.add(L(.64,.4,.035,.014),"#1d2027",{x:ue.x+.6,y:1.32,z:ue.z},"satin"),l.add(L(.5,.04,.35,.01),a.metal,{x:ue.x-1.2,y:1.11,z:ue.z+.1},"metal"),l.add(L(.46,.07,.44,.03),a.seat,{x:Ws.x,y:.29,z:Ws.z},"matte"),l.add(L(.44,.46,.06,.03),a.chair,{x:Ws.x,y:.62,z:Ws.z-.23},"matte"),l.add(Ht(.025,.025,.2,10),"#5d6470",{x:Ws.x,y:.16,z:Ws.z},"metal"),l.add(L(2,.5,.05,.02),r?"#2b2f38":"#e9e4dc",{x:ue.x-.4,y:1.95,z:Wt.z0+.03},"satin",!1),l.add(L(1.8,.08,.02),n.accent,{x:ue.x-.4,y:1.95,z:Wt.z0+.06},"glow",!1),l.add(L(.04,1.3,ys.length+.08,.012),"#aeb5bf",{x:Wt.x0+.04,y:1.55,z:ys.z},"metal",!1),l.add(L(.02,1.2,ys.length),r?"#26303a":"#fcfcfa",{x:Wt.x0+.07,y:1.55,z:ys.z},"satin",!1),l.add(L(3.2,.08,.5,.03),a.seat,{x:Bn.x,y:.45,z:Bn.z},"matte"),l.add(L(3.2,.5,.08,.03),a.seat,{x:Bn.x,y:.72,z:Bn.z+.24},"matte");for(let u of[-1.45,0,1.45])l.add(L(.06,.45,.4),a.metal,{x:Bn.x+u,y:.22,z:Bn.z},"metal",!1);l.add(L(.08,2.3,.08),a.metal,{x:vs.x-.8,y:1.15,z:vs.z},"metal"),l.add(L(.08,2.3,.08),a.metal,{x:vs.x+.8,y:1.15,z:vs.z},"metal"),l.add(L(1.68,.1,.1),a.metal,{x:vs.x,y:2.3,z:vs.z},"metal"),qi(l,r,-5.4,4,!0),qi(l,r,1.9,-3.9),t.add(nn(l,e));let c=new Ae({color:"#0e1420",emissive:a.dim,emissiveIntensity:.35,roughness:.3}),h=new Xt(L(.58,.34,.008),c);h.userData.shared=!0,h.position.set(ue.x+.6,1.32,ue.z-.02),h.rotation.y=Math.PI,t.add(h);let p=new ae;t.add(p);let d=new Xt(new de(ue.width,1.1,.6),new Te({visible:!1}));d.position.set(ue.x,.55,ue.z+.1),t.add(d),i.pickable(d,"route:settings");let f=new Xt(new de(.1,1.3,ys.length),new Te({visible:!1}));f.position.set(Wt.x0+.06,1.55,ys.z),t.add(f),i.pickable(f,"route:settings");let _=-1,b=!1,m=!1;return{frame:{min:{x:Wt.x0,y:0,z:Wt.z0},max:{x:Wt.x1,y:2.5,z:Wt.z1},polar:.98,azimuth:.62},lamps:[{x:0,y:2.2,z:-1.6},{x:-3.6,y:2.2,z:2.2},{x:3.2,y:2.2,z:2}],floor:{grid:new $n([{x0:ue.x-ue.width/2,x1:ue.x+ue.width/2,z0:ue.z-.2,z1:ue.z+.4},{x0:Bn.x-1.6,x1:Bn.x+1.6,z0:Bn.z,z1:Bn.z+.3}]),door:{x:vs.x,z:vs.z-.2}},update({model:u,t:S}){b=u.enabled,m=u.error;let R=[];u.enabled&&R.push({id:"reception",name:S("places.desk.receptionist"),state:u.error?"failed":u.pairing?"waiting":u.outgoing>0?"working":"idle",stateLabel:u.error?S("places.desk.error"):u.pairing?S("places.desk.pairing"):u.outgoing>0?S("places.desk.sending",{count:u.outgoing}):u.running?S("places.desk.open"):S("places.desk.starting"),look:Ti("legal"),place:Ws,action:u.error?"slump":u.pairing?"raise":u.outgoing>0?"talk":"rest",...u.pairing?{bubble:"\u2026"}:u.error?{bubble:"!"}:{},pick:"route:settings"});let v=0,M=0;for(let A of u.phones){if(!A.online&&!A.recent)continue;let g=A.recent!==null&&v<3;R.push({id:`phone-${A.id}`,name:A.name,state:g?"working":"idle",stateLabel:S(g?`places.desk.action.${A.recent}`:"places.desk.waiting"),look:Ti(`phone:${A.id}`),place:g?x_(v++):__(M++%4),action:g?"talk":"rest",pick:"route:settings"})}if(_!==Math.min(4,u.outgoing)){_=Math.min(4,u.outgoing);for(let g of[...p.children])g.removeFromParent(),Mn(g);let A=new ie;for(let g=0;g<_;g+=1)A.add(L(.3,.14,.22,.015),"#c9a47a",{x:ue.x-1.2+g%2*.05,y:1.2+g*.15,z:ue.z+.1,ry:g*.3},"matte"),A.add(L(.31,.02,.05),n.accent,{x:ue.x-1.2+g%2*.05,y:1.2+g*.15+.07,z:ue.z+.1,ry:g*.3},"satin",!1);_>0&&p.add(nn(A,e))}let E={};return u.phones.slice(0,6).forEach((A,g)=>{E[`badge-${A.id}`]={at:{x:Wt.x0+.1,y:2.05-g*.2,z:ys.z},title:A.name,detail:A.online?S("places.desk.online"):S("places.desk.offline"),...A.online?{tone:"busy"}:{},pick:"route:settings"}}),u.phones.length===0&&(E.none={at:{x:Wt.x0+.1,y:1.7,z:ys.z},title:S("places.desk.noPhones"),pick:"route:settings"}),u.enabled||(E.closed={at:{x:ue.x,y:1.5,z:ue.z},title:S("places.desk.closed"),detail:S("places.desk.closedHint"),pick:"route:settings"}),{people:R,labels:E}},tick(u){return c.emissive.set(m?"#8a2b24":b?r?"#3d7bd9":"#4b8fe6":a.dim),c.emissiveIntensity=b?.75+(s?0:Math.sin(u*2)*.05):.2,!1},dispose(){o.dispose();for(let u of[...t.children])Mn(u);c.dispose();for(let u of[d,f])u.material.dispose()}}};var Kn=i=>({x:-4.2+i%4*2.8,z:i<4?-1.5:1.6}),ci={x:-2.4,y:1.75},Ua={x:2.2,width:3.2},y_=i=>{let{x:t,z:e}=Kn(i);return{x:t,z:e-.75,face:{x:t,z:e+2},sit:!0}},v_=i=>{let{x:t,z:e}=Kn(i);return{x:t+.85,z:e-.6,face:{x:ci.x,z:-9},sit:!1}},b_={running:"type",soon:"rest",idle:"rest",failed:"slump",done:"rest",off:"rest"},Yd=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Fn(r),o=wi("carpet",r,Wt,2);t.add(o.mesh);let l=new ie;Ur(l,r),l.add(Ht(.55,.55,.05,40),"#fbfaf7",{x:ci.x,y:ci.y,z:Wt.z0+.05,rx:Math.PI/2},"satin",!1),l.add(cn(.55,.04,Math.PI*2,6,40),"#3b3b40",{x:ci.x,y:ci.y,z:Wt.z0+.07},"metal",!1);for(let u=0;u<12;u+=1){let S=u/12*Math.PI*2;l.add(L(.03,u%3===0?.1:.06,.01),"#3b3b40",{x:ci.x+Math.sin(S)*.44,y:ci.y+Math.cos(S)*.44,z:Wt.z0+.08,rz:-S},"matte",!1)}l.add(L(Ua.width+.08,1.3,.04,.012),"#aeb5bf",{x:Ua.x,y:1.65,z:Wt.z0+.03},"metal",!1),l.add(L(Ua.width,1.2,.02),r?"#26303a":"#fcfcfa",{x:Ua.x,y:1.65,z:Wt.z0+.055},"satin",!1);let c=Array.from({length:8},(u,S)=>Ol(l,r,Kn(S).x,Kn(S).z));l.add(L(1.2,.85,.5,.02),a.wood,{x:-5,y:.42,z:3.9},"satin"),l.add(L(.3,.36,.26,.03),"#2b2e36",{x:-5.2,y:1.03,z:3.9},"metal");for(let u of[.1,.25])l.add(Ht(.045,.04,.1,14),"#fbfaf7",{x:-5+u,y:.9,z:3.9},"satin",!1);qi(l,r,5.4,3.9,!0),qi(l,r,5.5,-4),t.add(nn(l,e));let h=new Ae({color:"#25252a",roughness:.5}),p=new de(.05,.3,.015).translate(0,.13,0),d=new de(.035,.45,.015).translate(0,.2,0),f=new Xt(p,h),_=new Xt(d,h);f.position.set(ci.x,ci.y,Wt.z0+.1),_.position.set(ci.x,ci.y,Wt.z0+.11),t.add(f,_);let b=c.map(u=>{let S=new Ae({color:"#0e1420",emissive:a.dim,emissiveIntensity:.3,roughness:.3}),R=new Xt(L(.58,.34,.008),S);return R.userData.shared=!0,R.position.copy(u),t.add(R),S});for(let u=0;u<8;u+=1){let S=new Xt(new de(1.2,1.1,1.5),new Te({visible:!1}));S.position.set(Kn(u).x,.55,Kn(u).z-.35),t.add(S),i.pickable(S,"route:schedules")}let m=[];return{frame:{min:{x:Wt.x0,y:0,z:Wt.z0},max:{x:Wt.x1,y:2.4,z:Wt.z1},polar:.98,azimuth:.62},lamps:[{x:-2.8,y:2.2,z:-1.6},{x:2.8,y:2.2,z:-1.6},{x:-2.8,y:2.2,z:1.6},{x:2.8,y:2.2,z:1.6}],floor:{grid:new $n([...Array.from({length:8},(u,S)=>({x0:Kn(S).x-.6,x1:Kn(S).x+.6,z0:Kn(S).z-.35,z1:Kn(S).z+.35})),{x0:-5.6,x1:-4.4,z0:3.65,z1:4.15}]),door:{x:5.2,z:4.2}},update({model:u,t:S}){m=u.officers;let R=m.flatMap((M,E)=>M.state==="off"?[]:[{id:M.id,name:M.title||S("places.duty.untitled"),state:M.state==="running"?"working":M.state==="failed"?"failed":M.state==="done"?"done":M.state==="soon"?"waiting":"idle",stateLabel:S(`places.duty.state.${M.state}`),look:Ti(`schedule:${M.id}`),place:M.state==="soon"?v_(E):y_(E),action:b_[M.state],...M.state==="failed"?{bubble:"!"}:M.state==="done"?{bubble:"\u2713"}:{},pick:"route:schedules"}]),v={};return m.forEach((M,E)=>{M.state==="off"&&(v[`off-${M.id}`]={at:{x:Kn(E).x,y:1.3,z:Kn(E).z},title:M.title||S("places.duty.untitled"),detail:S("places.duty.state.off"),pick:"route:schedules"})}),u.upcoming.slice(0,4).forEach((M,E)=>{let A=new Date(M.at),g=Number.isNaN(A.getTime())?M.at:A.toLocaleString(void 0,{weekday:"short",hour:"2-digit",minute:"2-digit"});v[`next-${M.id}`]={at:{x:Ua.x,y:2.15-E*.28,z:Wt.z0+.1},title:g,detail:M.title,pick:"route:schedules"}}),m.length===0&&(v.empty={at:{x:0,y:1.3,z:0},title:S("places.duty.empty"),pick:"route:schedules"}),u.more>0&&(v.more={at:{x:4.6,y:1,z:3.2},title:S("places.duty.more",{count:u.more})}),{people:R,labels:v}},tick(u){let S=new Date;return _.rotation.z=-((S.getMinutes()+S.getSeconds()/60)/60)*Math.PI*2,f.rotation.z=-((S.getHours()%12+S.getMinutes()/60)/12)*Math.PI*2,b.forEach((R,v)=>{let M=m[v],E=M?.state==="running";R.emissive.set(E?r?"#3d7bd9":"#4b8fe6":M?.state==="failed"?"#8a2b24":a.dim),R.emissiveIntensity=E?.9+(s?0:Math.sin(u*7+v)*.08):M&&M.state!=="off"?.45:.15}),!1},dispose(){o.dispose();for(let u of[...t.children])Mn(u);h.dispose();for(let u of b)u.dispose();t.traverse(u=>{u instanceof Xt&&u.material instanceof Te&&!u.material.visible&&u.material.dispose()})}}};var Ri=1.9,Sn=2.2,Xs=.42,wh=4,Vl=.52,Th=[2,1,3,0],Ci=i=>-4.6+i*2.3,hi=Wt.z0+Xs/2+.04,De={x:Wt.x0+.24,z0:-2.6,z1:.6},Jn=[{x:-1.3,z:.9},{x:2.1,z:.9}],ui={x:3.9,z:3.3},Ke={x:1.9,z:3.5},di={x:5.3,z:1.6},Ah={pdf:"#b5523b",word:"#3d6fa5",sheet:"#4f8a5b",slides:"#e0a13a",web:"#7b5ea7",text:"#c06c84",image:"#2f4858",other:"#8a8d3b"},$d=i=>({x:Ci(i),z:hi+.85,face:{x:Ci(i),z:-9},sit:!1}),Kd={x:De.x+.75,z:(De.z0+De.z1)/2,face:{x:-9,z:(De.z0+De.z1)/2},sit:!1},M_={x:Jn[0].x-.5,z:Jn[0].z-.72,face:{x:Jn[0].x-.5,z:5},sit:!0},S_={x:ui.x,z:ui.z-.75,face:{x:ui.x,z:6},sit:!0},E_={x:Ke.x,z:Ke.z-.65,face:{x:Ke.x,z:6},sit:!1},w_={x:di.x-.7,z:di.z,face:{x:9,z:di.z},sit:!1},Jd=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Fn(r),o=wi("wood",r,Wt,3);t.add(o.mesh);let l=new ie;Ur(l,r,{wall:r?"#4a4f5f":"#efe6d8",low:r?"#3f4454":"#e2d5c2"});for(let P=0;P<5;P+=1){let V=Ci(P);for(let z of[-1,1])l.add(L(.05,Sn,Xs,.01),a.wood,{x:V+z*(Ri/2),y:Sn/2,z:hi},"satin");l.add(L(Ri,Sn,.03),a.woodLight,{x:V,y:Sn/2,z:hi-Xs/2+.015},"matte",!1);for(let z=0;z<=wh;z+=1)l.add(L(Ri,.035,Xs,.008),a.wood,{x:V,y:.06+z*Vl,z:hi},"satin");l.add(L(Ri+.1,.08,Xs+.06,.02),a.wood,{x:V,y:Sn+.04,z:hi},"satin")}let c=De.z1-De.z0;for(let P of[De.z0,De.z1])l.add(L(.42,Sn,.05,.01),a.wood,{x:De.x,y:Sn/2,z:P},"satin");for(let P=0;P<=wh;P+=1)l.add(L(.42,.035,c,.008),a.wood,{x:De.x,y:.06+P*Vl,z:(De.z0+De.z1)/2},"satin");for(let P of Jn){l.add(L(2.4,.06,.95,.02),a.wood,{x:P.x,y:.72,z:P.z},"satin");for(let[V,z]of[[-1.1,-.38],[1.1,-.38],[-1.1,.38],[1.1,.38]])l.add(L(.07,.7,.07),a.woodLight,{x:P.x+V,y:.35,z:P.z+z},"satin");for(let V of[-.5,.5]){for(let z of[-1,1]){let X=P.z+z*.72;l.add(L(.42,.06,.4,.02),a.seat,{x:P.x+V,y:.46,z:X},"matte"),l.add(L(.42,.42,.05,.02),a.wood,{x:P.x+V,y:.7,z:X+z*.2},"satin");for(let[G,Y]of[[-.17,-.15],[.17,-.15],[-.17,.15],[.17,.15]])l.add(L(.035,.44,.035),a.woodLight,{x:P.x+V+G,y:.22,z:X+Y},"satin",!1)}l.add(Ht(.06,.07,.02,12),"#b08d3c",{x:P.x+V,y:.76,z:P.z},"metal",!1),l.add(Ht(.012,.012,.26,6),"#b08d3c",{x:P.x+V,y:.88,z:P.z},"metal",!1),l.add(L(.3,.07,.12,.03),"#2f6b48",{x:P.x+V,y:1.02,z:P.z},r?"glow":"satin",!1)}}let h=Ol(l,r,ui.x,ui.z,1.8);l.add(L(.9,.05,.5,.01),a.metal,{x:Ke.x,y:.75,z:Ke.z},"metal"),l.add(L(.9,.05,.5,.01),a.metal,{x:Ke.x,y:.35,z:Ke.z},"metal");for(let[P,V]of[[-.42,-.22],[.42,-.22],[-.42,.22],[.42,.22]])l.add(L(.03,.75,.03),a.metal,{x:Ke.x+P,y:.42,z:Ke.z+V},"metal",!1),l.add(Ht(.04,.04,.03,10),"#2a2d35",{x:Ke.x+P,y:.04,z:Ke.z+V,rz:Math.PI/2},"satin",!1);l.add(L(.7,.9,.6,.03),r?"#c9ccd2":"#eef0f3",{x:di.x,y:.45,z:di.z},"satin"),l.add(L(.62,.04,.5,.01),"#3a3f4b",{x:di.x,y:.92,z:di.z},"satin",!1),qi(l,r,-5.4,4,!0),qi(l,r,5.5,-2.9),t.add(nn(l,e));let p=430,d=new Ae({roughness:.8}),f=new ki(new de(1,1,1),d,p);f.castShadow=!0,f.count=0,t.add(f);let _=new Te({color:n.accent,toneMapped:!1}),b=new ki(new de(1,1,1),_,360);b.count=0,t.add(b);let m=new ae;t.add(m);let u=new yi("#ffd9a0",0,3,1.6);u.position.set(Jn[0].x-.5,1.2,Jn[0].z),t.add(u);let S=new Ae({color:"#0e1420",emissive:a.dim,emissiveIntensity:.4,roughness:.3}),R=new Xt(L(.58,.34,.008),S);R.userData.shared=!0,R.position.copy(h),t.add(R);for(let P=0;P<5;P+=1){let V=new Xt(new de(Ri,Sn,Xs),new Te({visible:!1}));V.position.set(Ci(P),Sn/2,hi),t.add(V),i.pickable(V,"route:knowledge")}let v=new Xt(new de(.42,Sn,c),new Te({visible:!1}));v.position.set(De.x,Sn/2,(De.z0+De.z1)/2),t.add(v),i.pickable(v,"route:workspace");let M=new be,E=new jt,A=new Xe,g=new zn,w=(P,V,z,X,G,Y,tt,et,dt=0)=>{A.setFromEuler(g.set(0,0,dt)),M.compose(new O(V,z,X),A,new O(G,Y,tt)),f.setMatrixAt(P,M),f.setColorAt(P,E.set(et))},T=P=>.045+Math.min(.06,Math.log2(1+P.size)*.008),I=P=>{let V=0,z=0;P.cases.forEach((Y,tt)=>{let et=0,dt=Th[0],Dt=Ci(tt)-Ri/2+.08;for(let Pt of Y.books){let xt=T(Pt);if(Dt+xt>Ci(tt)+Ri/2-.06){if(et+=1,et>=Th.length)break;dt=Th[et],Dt=Ci(tt)-Ri/2+.08}let q=.36+vh(Pt.id)*.1,it=.08+dt*Vl+q/2,gt=Pt.cited?.08:0;w(V++,Dt+xt/2,it,hi+.02+gt,xt,q,.24,Ah[Pt.kind]),Pt.cited&&(M.compose(new O(Dt+xt/2,it+q/2+.03,hi+.14+gt),A.identity(),new O(Math.max(.012,xt*.4),.08,.01)),b.setMatrixAt(z++,M)),Dt+=xt+.006}});let X=wh-1,G=De.z0+.06;for(let Y of P.papers.books){if(G+.03>De.z1-.06&&(X-=1,G=De.z0+.06,X<0))break;w(V++,De.x+.04,.08+X*Vl+.15,G+.012,.25,.3,.024,vh(Y.id)>.5?"#e8e2d2":"#d9cdb4"),G+=.03}return P.cart.forEach((Y,tt)=>{let et=Y.state==="failed",dt=Ke.x-.36+tt%5*.17,Dt=tt<5?.79:.39;w(V++,dt,Dt+(et?.02:.13),Ke.z,et?.24:.05,et?.04:.26,et?.18:.2,et?"#8a8f98":new jt(Ah[Y.kind]).lerp(new jt("#ffffff"),.35).getStyle())}),f.count=V,b.count=z,f.instanceMatrix.needsUpdate=!0,f.instanceColor&&(f.instanceColor.needsUpdate=!0),b.instanceMatrix.needsUpdate=!0,z},N=!1,B=!1,F=0;return{frame:{min:{x:Wt.x0,y:0,z:Wt.z0},max:{x:Wt.x1,y:Sn+.2,z:Wt.z1},polar:.98,azimuth:.62},lamps:[{x:-2.3,y:2.2,z:-2.6},{x:2.3,y:2.2,z:-2.6},{x:.4,y:2,z:1},{x:3.9,y:1.9,z:3}],floor:{grid:new $n([...Array.from({length:5},(P,V)=>({x0:Ci(V)-Ri/2,x1:Ci(V)+Ri/2,z0:Wt.z0,z1:hi+Xs/2})),{x0:Wt.x0,x1:De.x+.21,z0:De.z0,z1:De.z1},...Jn.map(P=>({x0:P.x-1.2,x1:P.x+1.2,z0:P.z-.48,z1:P.z+.48})),{x0:ui.x-.9,x1:ui.x+.9,z0:ui.z-.35,z1:ui.z+.35},{x0:Ke.x-.45,x1:Ke.x+.45,z0:Ke.z-.25,z1:Ke.z+.25},{x0:di.x-.35,x1:di.x+.35,z0:di.z-.3,z1:di.z+.3}]),door:{x:5.4,z:4.2}},update({model:P,t:V,lead:z,visitors:X=[]}){I(P);let G=[],{librarian:Y}=P,tt=P.cases.findIndex(xt=>xt.id===Y.caseId),et=Y.state==="searching"?$d(Math.max(0,tt)):Y.state==="papers"?Kd:Y.state==="reading"?M_:Y.state==="adding"?E_:S_;G.push({id:"librarian",name:z,state:Y.state==="idle"?"idle":"working",stateLabel:V(`places.library.librarian.${Y.state}`),look:Ti("lead"),place:et,action:Y.state==="searching"||Y.state==="papers"?"read":Y.state==="reading"?"paper":Y.state==="adding"?"operate":"rest",pick:"agent"}),P.clerk&&G.push({id:"clerk",name:V("places.library.clerk"),state:"working",stateLabel:V("places.library.reading",{count:P.cart.filter(xt=>xt.state!=="failed").length}),look:Ti("teacher"),place:w_,action:"operate",pick:"route:knowledge"});let Dt=[...Array.from({length:5},(xt,q)=>[$d(q),"read"]),[Kd,"read"],...[-.5,.5].map(xt=>[{x:Jn[1].x+xt,z:Jn[1].z-.72,face:{x:Jn[1].x+xt,z:5},sit:!0},"paper"])].filter(([xt])=>xt.x!==et.x||xt.z!==et.z);if(X.slice(0,Dt.length).forEach((xt,q)=>{let[it,gt]=Dt[q];G.push({id:xt.id,name:xt.name,state:"working",stateLabel:xt.stateLabel,look:xt.look,place:it,action:gt,pick:xt.pick})}),N=Y.state==="reading",B=Y.state!=="idle",F!==(N?Math.min(6,Y.cited):0)){F=N?Math.min(6,Y.cited):0;for(let q of[...m.children])q.removeFromParent(),Mn(q);let xt=new ie;for(let q=0;q<F;q+=1)xt.add(L(.24,.05,.3,.008),Object.values(Ah)[q%8],{x:Jn[0].x-.05,y:.775+q*.052,z:Jn[0].z-.1,ry:q%3*.12},"matte");F>0&&m.add(nn(xt,e))}let Pt={};if(P.cases.forEach((xt,q)=>{Pt[`case-${xt.id}`]={at:{x:Ci(q),y:Sn+.25,z:hi},title:xt.name,detail:V("places.library.documents",{count:xt.total}),...Y.caseId===xt.id&&Y.state!=="idle"?{tone:"busy"}:{},pick:"route:knowledge"}}),P.cases.length===0&&(Pt.empty={at:{x:0,y:Sn+.25,z:hi},title:V("places.library.empty"),pick:"route:knowledge"}),P.papers.total>0&&(Pt.papers={at:{x:De.x,y:Sn+.25,z:(De.z0+De.z1)/2},title:V("places.library.papers"),detail:V("places.library.paperCount",{count:P.papers.total}),pick:"route:workspace"}),P.cart.length>0){let xt=P.cart.filter(q=>q.state==="failed").length;Pt.cart={at:{x:Ke.x,y:1.1,z:Ke.z},title:V("places.library.cart"),detail:xt>0?V("places.library.failed",{count:xt}):V("places.library.reading",{count:P.cart.length}),tone:xt>0?"alert":"busy",pick:"route:knowledge"}}return P.enabled||(Pt.off={at:{x:ui.x,y:1.4,z:ui.z},title:V("places.library.off"),tone:"alert",pick:"route:knowledge"}),{people:G,labels:Pt}},tick(P){return u.intensity+=((N?r?5:2:0)-u.intensity)*(s?1:.08),S.emissive.set(B?r?"#3d7bd9":"#4b8fe6":a.dim),S.emissiveIntensity=B?.9+(s?0:Math.sin(P*5)*.08):.35,!1},dispose(){o.dispose();for(let P of[...t.children])P!==f&&P!==b&&Mn(P);f.geometry.dispose(),b.geometry.dispose(),d.dispose(),_.dispose(),S.dispose(),u.dispose(),t.traverse(P=>{P instanceof Xt&&P.material instanceof Te&&!P.material.visible&&P.material.dispose()})}}};var Hr={x0:-3.5,x1:4.1,z0:-2.7,z1:3.9},Gl=4,Wl=.24,Ms=.36,Fa=.26,Be={x:-4.85,z:-3.55},gn={x:4.9,z:-3.55},bs={x:5.2,z:4.2},Rh=4.6,A_={code:"#5b7db1",web:"#7b5ea7",doc:"#e3dccb",data:"#4f8a5b",config:"#9aa1ab",asset:"#c06c84",other:"#b8a48c"},Ch={x:Be.x+1.35,z:Be.z+.5,face:{x:0,z:2},sit:!1};function R_(i){let t=i>Gl?2:1,e=Math.min(Gl,Math.max(1,i)),n=(Hr.x1-Hr.x0-Wl*(e-1))/e,s=(Hr.z1-Hr.z0-Wl*(t-1))/t;return Array.from({length:i},(r,a)=>{let o=a%Gl,l=Math.floor(a/Gl),c=Hr.x0+o*(n+Wl),h=Hr.z0+l*(s+Wl);return{x0:c,x1:c+n,z0:h,z1:h+s,columns:Math.max(1,Math.floor((n-.1)/Ms))}})}var jd=i=>{let{root:t,finishes:e,options:n,still:s}=i,r=n.dark,a=Fn(r),o=wi("dirt",r,Wt,3);t.add(o.mesh);let l=new ie;l.add(L(Wt.x1-Wt.x0+.1,.12,Wt.z1-Wt.z0+.1),a.skirt,{y:-.3},"matte",!1);let c=r?"#8a93a3":"#9aa1ab";for(let et=Wt.x0;et<=Wt.x1+.01;et+=1.2)l.add(Ht(.04,.04,1.3,8),c,{x:et,y:.65,z:Wt.z0+.05},"metal");for(let et=Wt.z0;et<=Wt.z1+.01;et+=1.2)l.add(Ht(.04,.04,1.3,8),c,{x:Wt.x0+.05,y:.65,z:et},"metal");l.add(L(Wt.x1-Wt.x0,1.1,.02),r?"#3c4c5e":"#7d97b0",{y:.65,z:Wt.z0+.05},"glass",!1),l.add(L(.02,1.1,Wt.z1-Wt.z0),r?"#3c4c5e":"#7d97b0",{x:Wt.x0+.05,y:.65},"glass",!1);let h=r?"#c9a43a":"#e8c547";l.add(L(2.1,1.25,1.2,.03),h,{x:Be.x,y:.8,z:Be.z},"satin"),l.add(L(2.2,.08,1.3,.02),a.trim,{x:Be.x,y:1.46,z:Be.z},"satin");for(let et of[-.85,.85])l.add(L(.3,.18,1),"#7a7a7a",{x:Be.x+et,y:.09,z:Be.z},"matte");l.add(L(.7,.45,.02),a.sky,{x:Be.x-.35,y:.95,z:Be.z+.61},"glow",!1),l.add(L(.4,.95,.02),"#5d6470",{x:Be.x+.6,y:.66,z:Be.z+.61},"satin",!1),l.add(L(.5,.08,.3),"#7a7a7a",{x:Be.x+.6,y:.1,z:Be.z+.78},"matte"),l.add(L(.9,.3,.9,.02),"#7a7a7a",{x:gn.x,y:.15,z:gn.z},"matte");for(let et=.3;et<Rh;et+=.45){for(let[dt,Dt]of[[-.18,-.18],[.18,-.18],[-.18,.18],[.18,.18]])l.add(L(.04,.46,.04),"#e0a13a",{x:gn.x+dt,y:et+.22,z:gn.z+Dt},"metal",!1);l.add(L(.4,.03,.4),"#e0a13a",{x:gn.x,y:et,z:gn.z},"metal",!1)}t.add(nn(l,e));let p=new ae;p.position.set(gn.x,Rh,gn.z);let d=new ie;d.add(L(7.2,.18,.22),"#e0a13a",{x:-2.8},"metal"),d.add(L(1.4,.3,.5,.03),"#6b7280",{x:1.2,y:-.1},"metal"),d.add(L(.7,.55,.55,.03),r?"#c9ccd2":"#eef0f3",{x:.2,y:-.4},"satin"),p.add(nn(d,e));let f=new ae,_=new ie;_.add(Ht(.008,.008,1,4),"#2a2d35",{y:-.5},"metal",!1),f.add(nn(_,e)),p.add(f);let b=new ae,m=new ie;m.add(L(.1,.12,.1,.02),"#2a2d35",{},"metal"),b.add(nn(m,e)),p.add(b),t.add(p);let u=240,S=new Ae({roughness:.7}),R=new ki(new de(1,1,1).translate(0,.5,0),S,u);R.castShadow=!0,R.receiveShadow=!0,R.count=0,t.add(R);let v=new Ae({color:"#f08a24",transparent:!0,opacity:.38,roughness:.6,depthWrite:!1}),M=new ki(new de(1,1,1).translate(0,.5,0),v,u);M.count=0,t.add(M);let E=new ae;t.add(E);let A=new ae;t.add(A);let g=new Te({color:"#ff3b30",toneMapped:!1}),w=new Xt(L(.12,.12,.12,.03),g);w.userData.shared=!0,w.position.set(Be.x-.85,1.6,Be.z+.4),t.add(w);let T=[];i.pickable(R,et=>T[et]?`file:${T[et].path}`:void 0);let I=new Xt(new de(2.1,1.5,1.2),new Te({visible:!1}));I.position.set(Be.x,.8,Be.z),t.add(I),i.pickable(I,"route:changes");let N=new be,B=new jt,F=new Map,P=null,V=.4,z=!1,X="",G="",Y=et=>{let dt=R_(Math.min(8,et.districts.length)),Dt=dt.map(it=>`${it.x0.toFixed(2)},${it.z0.toFixed(2)}`).join("|");if(Dt!==X){X=Dt;for(let gt of[...E.children])gt.removeFromParent(),Mn(gt);let it=new ie;for(let gt of dt)it.add(L(gt.x1-gt.x0,.04,gt.z1-gt.z0,.01),r?"#4a4f5a":"#d6d2c8",{x:(gt.x0+gt.x1)/2,y:.02,z:(gt.z0+gt.z1)/2},"matte",!1);dt.length>0&&E.add(nn(it,e))}let Pt=0,xt=0;T=[],F.clear(),P=null;let q={};return et.districts.forEach((it,gt)=>{let zt=dt[gt];if(!zt)return;let Rt=Math.max(1,Math.floor((zt.z1-zt.z0-.1)/Ms)),Yt=Math.min(zt.columns,Math.max(1,Math.ceil(it.buildings.length/Rt),Math.ceil(Math.sqrt(it.buildings.length*(zt.x1-zt.x0)/(zt.z1-zt.z0))))),Me=Math.min(Rt,Math.ceil(it.buildings.length/Yt)),Qt=zt.x0+(zt.x1-zt.x0-Yt*Ms)/2,ne=zt.z0+(zt.z1-zt.z0-Me*Ms)/2;it.buildings.forEach((Kt,te)=>{let xe=te%Yt,ze=Math.floor(te/Yt),Ne=Qt+Ms/2+xe*Ms,ge=ne+Ms/2+ze*Ms;if(ge+Fa/2>zt.z1||Pt>=u)return;let Ee=.12+Kt.height*1.5;N.compose(new O(Ne,.04,ge),new Xe,new O(Fa,Ee,Fa)),R.setMatrixAt(Pt,N),R.setColorAt(Pt,B.set(Kt.editing?n.accent:A_[Kt.kind])),T[Pt]=Kt,Pt+=1,F.set(Kt.path,new O(Ne,Ee,ge)),Kt.editing&&(P=new O(Ne,Ee,ge)),(Kt.changed||Kt.conflict||Kt.editing)&&(N.compose(new O(Ne,.04,ge),new Xe,new O(Fa+.07,Ee+.12,Fa+.07)),M.setMatrixAt(xt,N),M.setColorAt(xt,B.set(Kt.conflict?"#e5534b":"#ffffff")),xt+=1)}),q[`district-${it.name}`]={at:{x:(zt.x0+zt.x1)/2,y:.5,z:zt.z1},title:it.name==="."?et.folder??".":it.name,detail:String(it.total)}}),R.count=Pt,M.count=xt,R.instanceMatrix.needsUpdate=!0,R.instanceColor&&(R.instanceColor.needsUpdate=!0),M.instanceMatrix.needsUpdate=!0,M.instanceColor&&(M.instanceColor.needsUpdate=!0),q},tt=et=>{if(A.children.length===et)return;for(let Dt of[...A.children])Dt.removeFromParent(),Mn(Dt);let dt=new ie;for(let Dt=0;Dt<et;Dt+=1){let Pt=bs.z-.9-Dt*1.25;dt.add(L(.75,.6,1,.04),"#f2f2f2",{x:bs.x,y:.45,z:Pt},"satin"),dt.add(L(.7,.5,.42,.05),"#3f88c5",{x:bs.x,y:.4,z:Pt+.72},"satin"),dt.add(L(.6,.18,.02),a.sky,{x:bs.x,y:.52,z:Pt+.94},"glow",!1);for(let[xt,q]of[[-.38,-.3],[.38,-.3],[-.38,.7],[.38,.7]])dt.add(Ht(.12,.12,.08,12),"#1d2027",{x:bs.x+xt,y:.12,z:Pt+q,rz:Math.PI/2},"satin")}et>0&&A.add(nn(dt,e))};return{frame:{min:{x:Wt.x0,y:0,z:Wt.z0},max:{x:Wt.x1,y:2.2,z:Wt.z1},polar:.92,azimuth:.62},lamps:[{x:-4.5,y:3,z:-3,colour:"#fff1d6"},{x:2,y:3,z:-3.6,colour:"#fff1d6"},{x:.5,y:3,z:2.5,colour:"#fff1d6"}],floor:{grid:new $n([{x0:Be.x-1.05,x1:Be.x+1.05,z0:Be.z-.6,z1:Be.z+.6},{x0:gn.x-.45,x1:gn.x+.45,z0:gn.z-.45,z1:gn.z+.45}]),door:bs},update({model:et,t:dt,lead:Dt,visitors:Pt=[]}){G=dt("places.site.uncommitted");let xt=Y(et);tt(Math.min(3,et.ahead)),z=et.checks.failed.length>0;let q=P,it=q&&et.worker.state==="editing"?{x:q.x-.32,z:q.z+.32,face:{x:q.x,z:q.z},sit:!1}:Ch,gt=[{id:"worker",name:Dt,state:et.worker.state==="idle"?"idle":"working",stateLabel:dt(`places.site.worker.${et.worker.state}`),look:{...Ti("lead"),accessory:"helmet"},place:it,action:et.worker.state==="editing"||et.worker.state==="testing"?"operate":et.worker.state==="reading"?"paper":"rest",pick:"agent"}],zt=[...F.values()];return Pt.forEach((Rt,Yt)=>{let Me=zt.length>0?zt[(Yt*7+3)%zt.length]:new O(Ch.x+.6*(Yt+1),0,Ch.z+.4);gt.push({id:Rt.id,name:Rt.name,state:"working",stateLabel:Rt.stateLabel,look:{...Rt.look,accessory:"helmet"},place:{x:Me.x+.3,z:Me.z+.3,face:{x:Me.x,z:Me.z},sit:!1},action:"operate",pick:Rt.pick})}),xt.office={at:{x:Be.x,y:1.75,z:Be.z},title:et.branch??dt("places.site.noGit"),detail:et.checks.running?dt("places.site.checking"):et.checks.failed.length>0?dt("places.site.checksFailed",{names:et.checks.failed.slice(0,3).join(", ")}):et.changed>0?dt("places.site.changed",{count:et.changed}):dt("places.site.clean"),...et.checks.failed.length>0?{tone:"alert"}:et.checks.running||et.worker.state!=="idle"?{tone:"busy"}:{},pick:"route:changes"},et.ahead>0&&(xt.gate={at:{x:bs.x,y:1,z:bs.z-1.2},title:dt("places.site.unpushed",{count:et.ahead}),pick:"route:changes"}),et.files===0&&(xt.empty={at:{x:.3,y:.6,z:.6},title:dt("places.site.empty")}),{people:gt,labels:xt}},tick(et,dt){let Dt=P,xt=(Dt?Math.atan2(-(Dt.z-gn.z),Dt.x-gn.x)+Math.PI:.4)-V;xt=Math.atan2(Math.sin(xt),Math.cos(xt));let q=Math.abs(xt)>.002;V+=s?xt:xt*Math.min(1,dt*1.5),p.rotation.y=V;let it=Dt?Math.min(6.5,Math.hypot(Dt.x-gn.x,Dt.z-gn.z)):3,gt=Math.max(.3,Dt?Rh-Dt.y-.4:1.8);return f.position.set(-it,0,0),f.scale.set(1,gt,1),b.position.set(-it,-gt-.06,0),g.color.set(z?s||Math.sin(et*6)>0?"#ff3b30":"#5a1a16":"#3a3f4b"),q},hover(et){if(!et.startsWith("file:"))return null;let dt=et.slice(5),Dt=F.get(dt),Pt=T.find(xt=>xt.path===dt);return Dt&&Pt?{at:{x:Dt.x,y:Dt.y+.15,z:Dt.z},title:dt,...Pt.changed?{detail:G,tone:"busy"}:{}}:null},dispose(){o.dispose();for(let et of[...t.children])et!==R&&et!==M&&Mn(et);R.geometry.dispose(),M.geometry.dispose(),S.dispose(),v.dispose(),g.dispose(),I.material.dispose()}}};var Qd={type:"change"},Ih={type:"start"},ef={type:"end"},Xl=new zs,tf=new Dn,C_=Math.cos(70*en.DEG2RAD),Je=new O,Cn=2*Math.PI,Re={NONE:-1,ROTATE:0,DOLLY:1,PAN:2,TOUCH_ROTATE:3,TOUCH_PAN:4,TOUCH_DOLLY_PAN:5,TOUCH_DOLLY_ROTATE:6},Ph=1e-6,Vr=class extends ya{constructor(t,e=null){super(t,e),this.state=Re.NONE,this.target=new O,this.cursor=new O,this.minDistance=0,this.maxDistance=1/0,this.minZoom=0,this.maxZoom=1/0,this.minTargetRadius=0,this.maxTargetRadius=1/0,this.minPolarAngle=0,this.maxPolarAngle=Math.PI,this.minAzimuthAngle=-1/0,this.maxAzimuthAngle=1/0,this.enableDamping=!1,this.dampingFactor=.05,this.enableZoom=!0,this.zoomSpeed=1,this.enableRotate=!0,this.rotateSpeed=1,this.keyRotateSpeed=1,this.enablePan=!0,this.panSpeed=1,this.screenSpacePanning=!0,this.keyPanSpeed=7,this.zoomToCursor=!1,this.autoRotate=!1,this.autoRotateSpeed=2,this.keys={LEFT:"ArrowLeft",UP:"ArrowUp",RIGHT:"ArrowRight",BOTTOM:"ArrowDown"},this.mouseButtons={LEFT:ds.ROTATE,MIDDLE:ds.DOLLY,RIGHT:ds.PAN},this.touches={ONE:fs.ROTATE,TWO:fs.DOLLY_PAN},this.target0=this.target.clone(),this.position0=this.object.position.clone(),this.zoom0=this.object.zoom,this._cursorStyle="auto",this._domElementKeyEvents=null,this._lastPosition=new O,this._lastQuaternion=new Xe,this._lastTargetPosition=new O,this._quat=new Xe().setFromUnitVectors(t.up,new O(0,1,0)),this._quatInverse=this._quat.clone().invert(),this._spherical=new Tn,this._sphericalDelta=new Tn,this._scale=1,this._panOffset=new O,this._rotateStart=new qt,this._rotateEnd=new qt,this._rotateDelta=new qt,this._panStart=new qt,this._panEnd=new qt,this._panDelta=new qt,this._dollyStart=new qt,this._dollyEnd=new qt,this._dollyDelta=new qt,this._dollyDirection=new O,this._mouse=new qt,this._performCursorZoom=!1,this._pointers=[],this._pointerPositions={},this._controlActive=!1,this._onPointerMove=I_.bind(this),this._onPointerDown=P_.bind(this),this._onPointerUp=L_.bind(this),this._onContextMenu=B_.bind(this),this._onMouseWheel=N_.bind(this),this._onKeyDown=U_.bind(this),this._onTouchStart=F_.bind(this),this._onTouchMove=O_.bind(this),this._onMouseDown=D_.bind(this),this._onMouseMove=z_.bind(this),this._interceptControlDown=k_.bind(this),this._interceptControlUp=H_.bind(this),this.domElement!==null&&this.connect(this.domElement),this.update()}set cursorStyle(t){this._cursorStyle=t,t==="grab"?this.domElement.style.cursor="grab":this.domElement.style.cursor="auto"}get cursorStyle(){return this._cursorStyle}connect(t){super.connect(t),this.domElement.addEventListener("pointerdown",this._onPointerDown),this.domElement.addEventListener("pointercancel",this._onPointerUp),this.domElement.addEventListener("contextmenu",this._onContextMenu),this.domElement.addEventListener("wheel",this._onMouseWheel,{passive:!1}),this.domElement.getRootNode().addEventListener("keydown",this._interceptControlDown,{passive:!0,capture:!0}),this.domElement.style.touchAction="none"}disconnect(){this.state=Re.NONE,this.domElement.removeEventListener("pointerdown",this._onPointerDown),this.domElement.ownerDocument.removeEventListener("pointermove",this._onPointerMove),this.domElement.ownerDocument.removeEventListener("pointerup",this._onPointerUp),this.domElement.removeEventListener("pointercancel",this._onPointerUp),this.domElement.removeEventListener("wheel",this._onMouseWheel),this.domElement.removeEventListener("contextmenu",this._onContextMenu),this.stopListenToKeyEvents();let t=this.domElement.getRootNode();t.removeEventListener("keydown",this._interceptControlDown,{capture:!0}),t.removeEventListener("keyup",this._interceptControlUp,{capture:!0}),this._controlActive=!1,this._pointers.length=0,this._pointerPositions={},this.domElement.style.touchAction="",this.domElement.style.cursor="auto"}dispose(){this.disconnect()}getPolarAngle(){return this._spherical.phi}getAzimuthalAngle(){return this._spherical.theta}getDistance(){return this.object.position.distanceTo(this.target)}listenToKeyEvents(t){t.addEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=t}stopListenToKeyEvents(){this._domElementKeyEvents!==null&&(this._domElementKeyEvents.removeEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=null)}saveState(){this.target0.copy(this.target),this.position0.copy(this.object.position),this.zoom0=this.object.zoom}reset(){this.target.copy(this.target0),this.object.position.copy(this.position0),this.object.zoom=this.zoom0,this.object.updateProjectionMatrix(),this.dispatchEvent(Qd),this.update(),this.state=Re.NONE}pan(t,e){this._pan(t,e),this.update()}dollyIn(t){this._dollyIn(t),this.update()}dollyOut(t){this._dollyOut(t),this.update()}rotateLeft(t){this._rotateLeft(t),this.update()}rotateUp(t){this._rotateUp(t),this.update()}update(t=null){let e=this.object.position;Je.copy(e).sub(this.target),Je.applyQuaternion(this._quat),this._spherical.setFromVector3(Je),this.autoRotate&&this.state===Re.NONE&&this._rotateLeft(this._getAutoRotationAngle(t)),this.enableDamping?(this._spherical.theta+=this._sphericalDelta.theta*this.dampingFactor,this._spherical.phi+=this._sphericalDelta.phi*this.dampingFactor):(this._spherical.theta+=this._sphericalDelta.theta,this._spherical.phi+=this._sphericalDelta.phi);let n=this.minAzimuthAngle,s=this.maxAzimuthAngle;isFinite(n)&&isFinite(s)&&(n<-Math.PI?n+=Cn:n>Math.PI&&(n-=Cn),s<-Math.PI?s+=Cn:s>Math.PI&&(s-=Cn),n<=s?this._spherical.theta=Math.max(n,Math.min(s,this._spherical.theta)):this._spherical.theta=this._spherical.theta>(n+s)/2?Math.max(n,this._spherical.theta):Math.min(s,this._spherical.theta)),this._spherical.phi=Math.max(this.minPolarAngle,Math.min(this.maxPolarAngle,this._spherical.phi)),this._spherical.makeSafe(),this.enableDamping===!0?this.target.addScaledVector(this._panOffset,this.dampingFactor):this.target.add(this._panOffset),this.target.sub(this.cursor),this.target.clampLength(this.minTargetRadius,this.maxTargetRadius),this.target.add(this.cursor);let r=!1;if(this.zoomToCursor&&this._performCursorZoom||this.object.isOrthographicCamera)this._spherical.radius=this._clampDistance(this._spherical.radius);else{let a=this._spherical.radius;this._spherical.radius=this._clampDistance(this._spherical.radius*this._scale),r=a!=this._spherical.radius}if(Je.setFromSpherical(this._spherical),Je.applyQuaternion(this._quatInverse),e.copy(this.target).add(Je),this.object.lookAt(this.target),this.enableDamping===!0?(this._sphericalDelta.theta*=1-this.dampingFactor,this._sphericalDelta.phi*=1-this.dampingFactor,this._panOffset.multiplyScalar(1-this.dampingFactor)):(this._sphericalDelta.set(0,0,0),this._panOffset.set(0,0,0)),this.zoomToCursor&&this._performCursorZoom){let a=null;if(this.object.isPerspectiveCamera){let o=Je.length();a=this._clampDistance(o*this._scale);let l=o-a;this.object.position.addScaledVector(this._dollyDirection,l),this.object.updateMatrixWorld(),r=!!l}else if(this.object.isOrthographicCamera){let o=new O(this._mouse.x,this._mouse.y,0);o.unproject(this.object);let l=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),this.object.updateProjectionMatrix(),r=l!==this.object.zoom;let c=new O(this._mouse.x,this._mouse.y,0);c.unproject(this.object),this.object.position.sub(c).add(o),this.object.updateMatrixWorld(),a=Je.length()}else console.warn("WARNING: OrbitControls.js encountered an unknown camera type - zoom to cursor disabled."),this.zoomToCursor=!1;a!==null&&(this.screenSpacePanning?this.target.set(0,0,-1).transformDirection(this.object.matrix).multiplyScalar(a).add(this.object.position):(Xl.origin.copy(this.object.position),Xl.direction.set(0,0,-1).transformDirection(this.object.matrix),Math.abs(this.object.up.dot(Xl.direction))<C_?this.object.lookAt(this.target):(tf.setFromNormalAndCoplanarPoint(this.object.up,this.target),Xl.intersectPlane(tf,this.target))))}else if(this.object.isOrthographicCamera){let a=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),a!==this.object.zoom&&(this.object.updateProjectionMatrix(),r=!0)}return this._scale=1,this._performCursorZoom=!1,r||this._lastPosition.distanceToSquared(this.object.position)>Ph||8*(1-this._lastQuaternion.dot(this.object.quaternion))>Ph||this._lastTargetPosition.distanceToSquared(this.target)>Ph?(this.dispatchEvent(Qd),this._lastPosition.copy(this.object.position),this._lastQuaternion.copy(this.object.quaternion),this._lastTargetPosition.copy(this.target),!0):!1}_getAutoRotationAngle(t){return t!==null?Cn/60*this.autoRotateSpeed*t:Cn/60/60*this.autoRotateSpeed}_getZoomScale(t){let e=Math.abs(t*.01);return Math.pow(.95,this.zoomSpeed*e)}_rotateLeft(t){this._sphericalDelta.theta-=t}_rotateUp(t){this._sphericalDelta.phi-=t}_panLeft(t,e){Je.setFromMatrixColumn(e,0),Je.multiplyScalar(-t),this._panOffset.add(Je)}_panUp(t,e){this.screenSpacePanning===!0?Je.setFromMatrixColumn(e,1):(Je.setFromMatrixColumn(e,0),Je.crossVectors(this.object.up,Je)),Je.multiplyScalar(t),this._panOffset.add(Je)}_pan(t,e){let n=this.domElement;if(this.object.isPerspectiveCamera){let s=this.object.position;Je.copy(s).sub(this.target);let r=Je.length();r*=Math.tan(this.object.fov/2*Math.PI/180),this._panLeft(2*t*r/n.clientHeight,this.object.matrix),this._panUp(2*e*r/n.clientHeight,this.object.matrix)}else this.object.isOrthographicCamera?(this._panLeft(t*(this.object.right-this.object.left)/this.object.zoom/n.clientWidth,this.object.matrix),this._panUp(e*(this.object.top-this.object.bottom)/this.object.zoom/n.clientHeight,this.object.matrix)):(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - pan disabled."),this.enablePan=!1)}_dollyOut(t){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale/=t:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_dollyIn(t){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale*=t:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_updateZoomParameters(t,e){if(!this.zoomToCursor)return;this._performCursorZoom=!0;let n=this.domElement.getBoundingClientRect(),s=t-n.left,r=e-n.top,a=n.width,o=n.height;this._mouse.x=s/a*2-1,this._mouse.y=-(r/o)*2+1,this._dollyDirection.set(this._mouse.x,this._mouse.y,1).unproject(this.object).sub(this.object.position).normalize()}_clampDistance(t){return Math.max(this.minDistance,Math.min(this.maxDistance,t))}_handleMouseDownRotate(t){this._rotateStart.set(t.clientX,t.clientY)}_handleMouseDownDolly(t){this._updateZoomParameters(t.clientX,t.clientX),this._dollyStart.set(t.clientX,t.clientY)}_handleMouseDownPan(t){this._panStart.set(t.clientX,t.clientY)}_handleMouseMoveRotate(t){this._rotateEnd.set(t.clientX,t.clientY),this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);let e=this.domElement;this._rotateLeft(Cn*this._rotateDelta.x/e.clientHeight),this._rotateUp(Cn*this._rotateDelta.y/e.clientHeight),this._rotateStart.copy(this._rotateEnd),this.update()}_handleMouseMoveDolly(t){this._dollyEnd.set(t.clientX,t.clientY),this._dollyDelta.subVectors(this._dollyEnd,this._dollyStart),this._dollyDelta.y>0?this._dollyOut(this._getZoomScale(this._dollyDelta.y)):this._dollyDelta.y<0&&this._dollyIn(this._getZoomScale(this._dollyDelta.y)),this._dollyStart.copy(this._dollyEnd),this.update()}_handleMouseMovePan(t){this._panEnd.set(t.clientX,t.clientY),this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd),this.update()}_handleMouseWheel(t){this._updateZoomParameters(t.clientX,t.clientY),t.deltaY<0?this._dollyIn(this._getZoomScale(t.deltaY)):t.deltaY>0&&this._dollyOut(this._getZoomScale(t.deltaY)),this.update()}_handleKeyDown(t){let e=!1;switch(t.code){case this.keys.UP:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateUp(Cn*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,this.keyPanSpeed),e=!0;break;case this.keys.BOTTOM:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateUp(-Cn*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,-this.keyPanSpeed),e=!0;break;case this.keys.LEFT:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateLeft(Cn*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(this.keyPanSpeed,0),e=!0;break;case this.keys.RIGHT:t.ctrlKey||t.metaKey||t.shiftKey?this.enableRotate&&this._rotateLeft(-Cn*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(-this.keyPanSpeed,0),e=!0;break}e&&(t.preventDefault(),this.update())}_handleTouchStartRotate(t){if(this._pointers.length===1)this._rotateStart.set(t.pageX,t.pageY);else{let e=this._getSecondPointerPosition(t),n=.5*(t.pageX+e.x),s=.5*(t.pageY+e.y);this._rotateStart.set(n,s)}}_handleTouchStartPan(t){if(this._pointers.length===1)this._panStart.set(t.pageX,t.pageY);else{let e=this._getSecondPointerPosition(t),n=.5*(t.pageX+e.x),s=.5*(t.pageY+e.y);this._panStart.set(n,s)}}_handleTouchStartDolly(t){let e=this._getSecondPointerPosition(t),n=t.pageX-e.x,s=t.pageY-e.y,r=Math.sqrt(n*n+s*s);this._dollyStart.set(0,r)}_handleTouchStartDollyPan(t){this.enableZoom&&this._handleTouchStartDolly(t),this.enablePan&&this._handleTouchStartPan(t)}_handleTouchStartDollyRotate(t){this.enableZoom&&this._handleTouchStartDolly(t),this.enableRotate&&this._handleTouchStartRotate(t)}_handleTouchMoveRotate(t){if(this._pointers.length==1)this._rotateEnd.set(t.pageX,t.pageY);else{let n=this._getSecondPointerPosition(t),s=.5*(t.pageX+n.x),r=.5*(t.pageY+n.y);this._rotateEnd.set(s,r)}this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);let e=this.domElement;this._rotateLeft(Cn*this._rotateDelta.x/e.clientHeight),this._rotateUp(Cn*this._rotateDelta.y/e.clientHeight),this._rotateStart.copy(this._rotateEnd)}_handleTouchMovePan(t){if(this._pointers.length===1)this._panEnd.set(t.pageX,t.pageY);else{let e=this._getSecondPointerPosition(t),n=.5*(t.pageX+e.x),s=.5*(t.pageY+e.y);this._panEnd.set(n,s)}this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd)}_handleTouchMoveDolly(t){let e=this._getSecondPointerPosition(t),n=t.pageX-e.x,s=t.pageY-e.y,r=Math.sqrt(n*n+s*s);this._dollyEnd.set(0,r),this._dollyDelta.set(0,Math.pow(this._dollyEnd.y/this._dollyStart.y,this.zoomSpeed)),this._dollyOut(this._dollyDelta.y),this._dollyStart.copy(this._dollyEnd);let a=(t.pageX+e.x)*.5,o=(t.pageY+e.y)*.5;this._updateZoomParameters(a,o)}_handleTouchMoveDollyPan(t){this.enableZoom&&this._handleTouchMoveDolly(t),this.enablePan&&this._handleTouchMovePan(t)}_handleTouchMoveDollyRotate(t){this.enableZoom&&this._handleTouchMoveDolly(t),this.enableRotate&&this._handleTouchMoveRotate(t)}_addPointer(t){this._pointers.push(t.pointerId)}_removePointer(t){delete this._pointerPositions[t.pointerId];for(let e=0;e<this._pointers.length;e++)if(this._pointers[e]==t.pointerId){this._pointers.splice(e,1);return}}_isTrackingPointer(t){for(let e=0;e<this._pointers.length;e++)if(this._pointers[e]==t.pointerId)return!0;return!1}_trackPointer(t){let e=this._pointerPositions[t.pointerId];e===void 0&&(e=new qt,this._pointerPositions[t.pointerId]=e),e.set(t.pageX,t.pageY)}_getSecondPointerPosition(t){let e=t.pointerId===this._pointers[0]?this._pointers[1]:this._pointers[0];return this._pointerPositions[e]}_customWheelEvent(t){let e=t.deltaMode,n={clientX:t.clientX,clientY:t.clientY,deltaY:t.deltaY};switch(e){case 1:n.deltaY*=16;break;case 2:n.deltaY*=100;break}return t.ctrlKey&&!this._controlActive&&(n.deltaY*=10),n}};function P_(i){this.enabled!==!1&&(this._pointers.length===0&&(this.domElement.setPointerCapture(i.pointerId),this.domElement.ownerDocument.addEventListener("pointermove",this._onPointerMove),this.domElement.ownerDocument.addEventListener("pointerup",this._onPointerUp)),!this._isTrackingPointer(i)&&(this._addPointer(i),i.pointerType==="touch"?this._onTouchStart(i):this._onMouseDown(i),this._cursorStyle==="grab"&&(this.domElement.style.cursor="grabbing")))}function I_(i){this.enabled!==!1&&(i.pointerType==="touch"?this._onTouchMove(i):this._onMouseMove(i))}function L_(i){switch(this._removePointer(i),this._pointers.length){case 0:this.domElement.releasePointerCapture(i.pointerId),this.domElement.ownerDocument.removeEventListener("pointermove",this._onPointerMove),this.domElement.ownerDocument.removeEventListener("pointerup",this._onPointerUp),this.dispatchEvent(ef),this.state=Re.NONE,this._cursorStyle==="grab"&&(this.domElement.style.cursor="grab");break;case 1:let t=this._pointers[0],e=this._pointerPositions[t];this._onTouchStart({pointerId:t,pageX:e.x,pageY:e.y});break}}function D_(i){let t;switch(i.button){case 0:t=this.mouseButtons.LEFT;break;case 1:t=this.mouseButtons.MIDDLE;break;case 2:t=this.mouseButtons.RIGHT;break;default:t=-1}switch(t){case ds.DOLLY:if(this.enableZoom===!1)return;this._handleMouseDownDolly(i),this.state=Re.DOLLY;break;case ds.ROTATE:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=Re.PAN}else{if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=Re.ROTATE}break;case ds.PAN:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=Re.ROTATE}else{if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=Re.PAN}break;default:this.state=Re.NONE}this.state!==Re.NONE&&this.dispatchEvent(Ih)}function z_(i){switch(this.state){case Re.ROTATE:if(this.enableRotate===!1)return;this._handleMouseMoveRotate(i);break;case Re.DOLLY:if(this.enableZoom===!1)return;this._handleMouseMoveDolly(i);break;case Re.PAN:if(this.enablePan===!1)return;this._handleMouseMovePan(i);break}}function N_(i){this.enabled===!1||this.enableZoom===!1||this.state!==Re.NONE||(i.preventDefault(),this.dispatchEvent(Ih),this._handleMouseWheel(this._customWheelEvent(i)),this.dispatchEvent(ef))}function U_(i){this.enabled!==!1&&this._handleKeyDown(i)}function F_(i){switch(this._trackPointer(i),this._pointers.length){case 1:switch(this.touches.ONE){case fs.ROTATE:if(this.enableRotate===!1)return;this._handleTouchStartRotate(i),this.state=Re.TOUCH_ROTATE;break;case fs.PAN:if(this.enablePan===!1)return;this._handleTouchStartPan(i),this.state=Re.TOUCH_PAN;break;default:this.state=Re.NONE}break;case 2:switch(this.touches.TWO){case fs.DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchStartDollyPan(i),this.state=Re.TOUCH_DOLLY_PAN;break;case fs.DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchStartDollyRotate(i),this.state=Re.TOUCH_DOLLY_ROTATE;break;default:this.state=Re.NONE}break;default:this.state=Re.NONE}this.state!==Re.NONE&&this.dispatchEvent(Ih)}function O_(i){switch(this._trackPointer(i),this.state){case Re.TOUCH_ROTATE:if(this.enableRotate===!1)return;this._handleTouchMoveRotate(i),this.update();break;case Re.TOUCH_PAN:if(this.enablePan===!1)return;this._handleTouchMovePan(i),this.update();break;case Re.TOUCH_DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchMoveDollyPan(i),this.update();break;case Re.TOUCH_DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchMoveDollyRotate(i),this.update();break;default:this.state=Re.NONE}}function B_(i){this.enabled!==!1&&i.preventDefault()}function k_(i){i.key==="Control"&&(this._controlActive=!0,this.domElement.getRootNode().addEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}function H_(i){i.key==="Control"&&(this._controlActive=!1,this.domElement.getRootNode().removeEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}var V_=1.35,G_=8,En=.5,nf=.2;function Oa(i,t){return`#${new jt(i).offsetHSL(0,0,t).getHexString()}`}var Gr=class{constructor(t,e,n,s,r){re(this,"root",new ae);re(this,"id");re(this,"position");re(this,"heading",0);re(this,"path",[]);re(this,"place",null);re(this,"doing","rest");re(this,"changedAt",0);re(this,"settledAt",0);re(this,"sit",0);re(this,"stride",0);re(this,"moving",!1);re(this,"blinkAt");re(this,"cheerUntil",0);re(this,"body",new ae);re(this,"head",new ae);re(this,"eyes");re(this,"legs");re(this,"arms");re(this,"book");re(this,"cup");re(this,"marker");re(this,"paper");re(this,"pages");re(this,"geometries",[]);re(this,"finishes");re(this,"phase");this.id=t,this.finishes=r,this.position={...n},this.phase=t.length*1.7%(Math.PI*2),this.blinkAt=1+Math.random()*3;let a="#2a2a2e";this.legs=[-.085,.085].map(b=>{let m=this.limb(.24,.2,u=>u.add(L(.13,.25,.13,.035),e.pants,{y:-.12}),u=>{u.add(L(.12,.2,.12,.03),e.pants,{y:-.1}),u.add(L(.135,.065,.21,.03),a,{y:-.225,z:.035}),u.add(L(.13,.015,.2,.006),"#e8e4dc",{y:-.255,z:.035})});return m.upper.position.set(b,En,0),this.body.add(m.upper),m});let o=new ie;o.add(L(.36,.42,.22,.06),e.shirt,{y:En+.21}),o.add(L(.37,.05,.23,.02),Oa(e.pants,-.08),{y:En+.02}),o.add(L(.05,.035,.01),"#c9a24a",{y:En+.02,z:.116}),o.add(L(.2,.05,.16,.02),Oa(e.shirt,.08),{y:En+.41}),o.add(Ht(.055,.06,.06,10),e.skin,{y:En+.45}),e.accessory==="tie"?(o.add(L(.07,.04,.02),"#9e2b25",{y:En+.37,z:.115}),o.add(L(.06,.22,.02,.008),"#9e2b25",{y:En+.24,z:.115})):e.accessory==="scarf"?(o.add(cn(.15,.045,Math.PI*2,8,16),"#e8c547",{y:En+.43,rx:Math.PI/2}),o.add(L(.07,.16,.03,.012),"#e8c547",{y:En+.33,z:.12,x:.07})):e.accessory==="badge"&&(o.add(L(.08,.09,.02,.008),s,{y:En+.32,z:.115,x:-.09}),o.add(L(.05,.012,.022),"#ffffff",{y:En+.33,z:.116,x:-.09})),this.body.add(this.meshOf(o)),this.arms=[-.235,.235].map(b=>{let m=this.limb(.19,.16,u=>u.add(L(.1,.2,.1,.03),e.shirt,{y:-.095}),u=>{u.add(L(.092,.16,.092,.028),e.shirt,{y:-.08}),u.add(L(.096,.025,.096,.01),Oa(e.shirt,-.06),{y:-.15}),u.add(L(.095,.09,.095,.035),e.skin,{y:-.205})});return m.end.position.y=-.205,m.upper.position.set(b,En+.38,0),this.body.add(m.upper),m}),this.head.position.y=En+.42+.2;let l=new ie;l.add(L(.38,.36,.36,.08),e.skin);for(let b of[-1,1])l.add(L(.04,.08,.07,.02),e.skin,{x:b*.195,y:-.01});l.add(L(.05,.05,.04,.018),Oa(e.skin,-.06),{y:-.03,z:.18}),l.add(L(.09,.022,.02,.008),"#a5574b",{y:-.1,z:.175});for(let b of[-1,1])l.add(L(.055,.03,.01,.01),"#f08f8f",{x:b*.12,y:-.06,z:.181});this.addHair(l,e),this.addHeadwear(l,e),this.head.add(this.meshOf(l));let c=new ie;for(let b of[-1,1])c.add(L(.05,.07,.02,.012),"#1d1d22",{x:b*.08}),c.add(L(.016,.018,.005),"#ffffff",{x:b*.08+.01,y:.016,z:.011});this.eyes=this.meshOf(c,!1),this.eyes.position.set(0,.02,.18),this.head.add(this.eyes),this.body.add(this.head);let h=new ie;h.add(L(.22,.28,.05,.01),"#b5523b"),h.add(L(.2,.26,.052),"#f3efe7",{x:.012}),this.book=this.meshOf(h),this.book.position.set(0,.62,.24),this.book.visible=!1,this.body.add(this.book);let p=new ie;p.add(Ht(.038,.034,.09,12),"#ffffff"),p.add(cn(.024,.007,Math.PI*2,6,10),"#ffffff",{x:.04}),this.cup=this.meshOf(p),this.cup.position.set(0,-.06,.06),this.cup.visible=!1,this.arms[1].end.add(this.cup);let d=new ie;d.add(Ht(.014,.014,.15,8),s,{rx:Math.PI/2}),d.add(Xi(.014,.03,8),"#1d1d22",{z:.09,rx:Math.PI/2}),this.marker=this.meshOf(d),this.marker.position.set(0,-.05,.08),this.marker.visible=!1,this.arms[1].end.add(this.marker);let f=new ie;f.add(L(.21,.29,.006),"#fbfaf6");for(let b=0;b<6;b+=1)f.add(L(.15-b%3*.02,.012,.002),"#9aa1ab",{y:.1-b*.035,z:.004});this.paper=this.meshOf(f,!1),this.paper.position.set(0,.64,.25),this.paper.rotation.x=-.35,this.paper.visible=!1,this.body.add(this.paper);let _=new ie;for(let b=0;b<4;b+=1)_.add(L(.21,.007,.29),"#fbfaf6",{y:b*.008,ry:b%2*.05});this.pages=this.meshOf(_),this.pages.position.set(0,.6,.27),this.pages.visible=!1,this.body.add(this.pages),this.root.add(this.body),this.root.position.set(n.x,0,n.z),this.root.userData.personId=t,this.root.traverse(b=>{b.userData.personId=t})}meshOf(t,e=!0){let[n]=t.build(),s=n.geometry;this.geometries.push(s);let r=new Xt(s,this.finishes.matte);return r.castShadow=e,r}limb(t,e,n,s){let r=new ae,a=new ie;n(a),r.add(this.meshOf(a));let o=new ae;o.position.y=-t;let l=new ie;s(l),o.add(this.meshOf(l));let c=new ae;return c.position.y=-e,o.add(c),r.add(o),{upper:r,lower:o,end:c}}addHair(t,e){let n=e.hair;if(e.hairStyle==="bald"){for(let s of[-1,1])t.add(L(.03,.12,.26,.012),n,{x:s*.19,y:.02,z:-.04});return}t.add(L(.4,.11,.38,.05),n,{y:.17}),t.add(L(.4,.22,.07,.03),n,{y:.07,z:-.165});for(let s of[-1,1])t.add(L(.03,.12,.2,.012),n,{x:s*.195,y:.1,z:-.05});if(e.hairStyle==="short"&&t.add(L(.3,.06,.05,.02),n,{y:.15,z:.17,rx:.3}),e.hairStyle==="long"&&(t.add(L(.42,.44,.09,.03),n,{y:-.03,z:-.175}),t.add(L(.36,.06,.05,.02),n,{y:.15,z:.17,rx:.2})),e.hairStyle==="bun"&&t.add(Xn(.09,12,10),n,{y:.27,z:-.12}),e.hairStyle==="spiky")for(let[s,r,a]of[[-.11,.06,-.3],[.02,-.06,0],[.12,.08,.3],[-.02,.14,.15],[.08,-.12,.2]])t.add(Xi(.065,.14,5),n,{x:s,y:.28,z:r,rz:a})}addHeadwear(t,e){let n="#1d1d22",s=e.accessory;if(s==="glasses"){for(let r of[-1,1])t.add(cn(.042,.009,Math.PI*2,6,16),n,{x:r*.08,y:.02,z:.19});t.add(L(.05,.012,.012),n,{y:.03,z:.19})}else if(s==="headset"){t.add(cn(.21,.018,Math.PI,6,16),n,{y:.06});for(let r of[-1,1])t.add(L(.05,.11,.11,.025),n,{x:r*.2});t.add(L(.02,.02,.15,.008),n,{x:.2,y:-.08,z:.08,ry:.4}),t.add(Xn(.022,8,6),"#38c98f",{x:.17,y:-.09,z:.15})}else s==="cap"?(t.add(L(.41,.11,.39,.05),e.shirt,{y:.21}),t.add(L(.36,.025,.17,.01),e.shirt,{y:.17,z:.24}),t.add(Xn(.025,8,6),Oa(e.shirt,.15),{y:.27})):s==="helmet"&&(t.add(Xn(.245,16,10),"#f2c230",{y:.12,sy:.75}),t.add(L(.5,.025,.5,.01),"#f2c230",{y:.1}))}get action(){return this.doing}set action(t){t!==this.doing&&(this.doing=t,this.changedAt=performance.now()/1e3)}goTo(t,e){this.place=t,this.path=e}get walking(){return this.moving}get seated(){return this.sit>.5}cheer(t){this.cheerUntil=t+1.4}get top(){return En+.84+.12-this.sit*nf}update(t,e,n){let s=this.moving;if(this.moving=!1,this.path.length>0){let l=this.path[0],c=l.x-this.position.x,h=l.z-this.position.z,p=Math.hypot(c,h),d=n?p:V_*t;p<=d||p<.01?(this.position.x=l.x,this.position.z=l.z,this.path.shift()):(this.position.x+=c/p*d,this.position.z+=h/p*d,this.turnToward(Math.atan2(c,h),t,n)),this.moving=this.path.length>0||p>d}s&&!this.moving&&(this.settledAt=e);let r=!this.moving&&this.place!==null;r&&this.place&&this.turnToward(Math.atan2(this.place.face.x-this.position.x,this.place.face.z-this.position.z),t,n);let a=r&&!!this.place?.sit&&!this.moving,o=n?1:1-Math.exp(-t*8);this.sit+=((a?1:0)-this.sit)*o,this.root.position.set(this.position.x,0,this.position.z),this.root.rotation.y=this.heading,this.pose(t,e,n)}turnToward(t,e,n){let s=t-this.heading;s=Math.atan2(Math.sin(s),Math.cos(s)),this.heading+=n?s:s*Math.min(1,e*G_)}pose(t,e,n){let[s,r]=this.legs,[a,o]=this.arms,l=e+this.phase;this.moving&&!n&&(this.stride+=t*9);let c=this.moving&&!n?Math.sin(this.stride):0,h=this.sit;s.upper.rotation.x=c*.55*(1-h)-Math.PI/2*h,r.upper.rotation.x=-c*.55*(1-h)-Math.PI/2*h,s.lower.rotation.x=Math.max(0,-c)*.6*(1-h)+Math.PI/2*h,r.lower.rotation.x=Math.max(0,c)*.6*(1-h)+Math.PI/2*h;let p=n||this.moving?0:Math.sin(l*1.6)*.004;this.body.position.y=-nf*h+(this.moving&&!n?Math.abs(Math.cos(this.stride))*.03:p),this.body.rotation.x=0;let d={x:-c*.5,z:-.06,elbow:-.15},f={x:c*.5,z:.06,elbow:-.15},_=0,b=0;this.book.visible=!1,this.cup.visible=!1,this.marker.visible=!1,this.paper.visible=!1,this.pages.visible=!1;let m=this.moving&&this.action!=="carry"?"walk":this.action,u=e-Math.max(this.settledAt,this.changedAt);if(e<this.cheerUntil&&!n){let v=Math.sin((this.cheerUntil-e)/1.4*Math.PI);d={x:0,z:-2.6,elbow:-.2},f={x:0,z:2.6,elbow:-.2},this.body.position.y+=v*.12}else if(m==="type"){let v=n?0:Math.sin(l*18)*.08;d={x:-1.05+v,z:.1,elbow:-.55},f={x:-1.05-v,z:-.1,elbow:-.55},_=.12+(n?0:Math.sin(l*2.1)*.03)}else if(m==="read"&&h<.5&&u<1.3&&!n){let v=Math.sin(Math.min(1,u/1.3)*Math.PI);f={x:-2.4*v,z:-.12,elbow:-.25},d={x:-.2,z:.08,elbow:-.3},_=-.18*v}else if(m==="read")d={x:-.95,z:.2,elbow:-.9},f={x:-.95,z:-.2,elbow:-.9},_=.3,this.book.visible=!0;else if(m==="browse"){let v=n?0:Math.max(0,Math.sin(l*.7))**8*.12;f={x:-1-v,z:-.2,elbow:-.55+v},d={x:-.8,z:.16,elbow:-.75},_=.1+(n?0:Math.sin(l*.45)*.04),b=n?0:Math.sin(l*.6)*.12}else if(m==="paper")d={x:-1,z:.16,elbow:-.85},f={x:-1,z:-.16,elbow:-.85},_=.26+(n?0:Math.sin(l*.5)*.04),this.paper.visible=!0;else if(m==="gaze")d={x:.45,z:.12,elbow:-.6},f={x:.45,z:-.12,elbow:-.6},_=-.1,b=n?0:Math.sin(l*.35)*.22;else if(m==="carry")d={x:-.75,z:.12,elbow:-.75},f={x:-.75,z:-.12,elbow:-.75},_=.12,this.pages.visible=!0;else if(m==="think")f={x:-1.6,z:-.35,elbow:-1.9},d={x:-.3,z:.25,elbow:-1.2},_=-.12,b=n?0:Math.sin(l*.9)*.15;else if(m==="write")f={x:-2.3+(n?0:Math.sin(l*3)*.15),z:-.2+(n?0:Math.cos(l*2.3)*.2),elbow:-.3},this.marker.visible=!0,b=n?0:Math.sin(l*1.1)*.12;else if(m==="talk")f={x:-.9+(n?0:Math.sin(l*2.6)*.25),z:-.15,elbow:-.9},d={x:-.4,z:.1,elbow:-.6},_=n?0:Math.sin(l*3.2)*.07,b=n?0:Math.sin(l*.7)*.25;else if(m==="raise")f={x:0,z:2.75+(n?0:Math.sin(l*6)*.18),elbow:-.25},_=-.1;else if(m==="slump")_=.45,d={x:.05,z:.04,elbow:0},f={x:.05,z:-.04,elbow:0};else if(m==="sip"){let v=n?0:Math.max(0,Math.sin(l*.8));f={x:-.5-v*1.2,z:-.15,elbow:-.6-v*1.4},this.cup.visible=!0}else if(m==="operate"){let v=n?0:Math.sin(l*12)*.1;d={x:-1.2+v,z:.12,elbow:-.4},f={x:-1.2-v,z:-.12,elbow:-.4},_=.05}else m==="rest"&&h>.5&&(d={x:-.5,z:.1,elbow:-.6},f={x:-.5,z:-.1,elbow:-.6});let R=n?1:1-Math.exp(-t*10);for(let[v,M]of[[a,d],[o,f]])v.upper.rotation.x+=(M.x-v.upper.rotation.x)*R,v.upper.rotation.z+=(M.z-v.upper.rotation.z)*R,v.lower.rotation.x+=(M.elbow-v.lower.rotation.x)*R;this.head.rotation.x+=(_-this.head.rotation.x)*R,this.head.rotation.y+=(b-this.head.rotation.y)*R,!n&&e>this.blinkAt&&(this.blinkAt=e+2.5+Math.random()*3.5),this.eyes.scale.y=!n&&e>this.blinkAt-.12?.15:1}dispose(){this.root.removeFromParent();for(let t of this.geometries)t.dispose()}};var jn=.18,W_=L(.58,.34,.008),X_=cn(.42,.025,Math.PI*2,8,40);function q_(i){let t=document.createElement("canvas");t.width=512,t.height=512;let e=t.getContext("2d");e.fillStyle=i?"#76604b":"#c9a37c",e.fillRect(0,0,512,512);for(let s=0;s<8;s+=1){let r=s%2*128;for(let a=-1;a<3;a+=1){let o=(s*7+a*3)%5/5;e.fillStyle=i?`rgba(0,0,0,${.08+o*.08})`:`rgba(90,55,25,${.05+o*.07})`,e.fillRect(a*256+r+2,s*64+2,252,60),e.fillStyle=i?"rgba(255,255,255,0.03)":"rgba(255,255,255,0.12)",e.fillRect(a*256+r+10,s*64+20+o*20,236,2)}}let n=new Hi(t);return n.wrapS=gi,n.wrapT=gi,n.repeat.set(3,2.2),n.colorSpace=He,n.anisotropy=4,n}function Y_(i){return i?{wall:"#4d5466",wallLow:"#434a5b",trim:"#262a33",skirt:"#2b2f38",sky:"#1d2e5c",frame:"#2c303a",deskTop:"#6b5a4a",deskFrame:"#3a3f4b",chair:"#2f3442",seat:"#3d4456",wood:"#4e3b2c",woodLight:"#5f4836",sofa:"#5a4b72",cushion:"#6d5d88",rug:"#3c3346",rugLounge:"#2f3a4a",pot:"#8a5a44",soil:"#3a2a20",leaf:"#4f8a5b",leafLight:"#6aa86f",counter:"#4e3b2c",top:"#6b5a4a",cooler:"#b9bfc8",lampShade:"#ffd9a0"}:{wall:"#f1ece4",wallLow:"#e6ddd0",trim:"#d9cfc1",skirt:"#e9e4dc",sky:"#bfe3ff",frame:"#e8e2d8",deskTop:"#e8dccb",deskFrame:"#9aa1ab",chair:"#4c5566",seat:"#5c677c",wood:"#a5784f",woodLight:"#bf9468",sofa:"#7f9cc0",cushion:"#9bb4d4",rug:"#d9cbe0",rugLounge:"#c9d6e3",pot:"#c1785a",soil:"#5a4030",leaf:"#4f8a5b",leafLight:"#6aa86f",counter:"#a5784f",top:"#e8dccb",cooler:"#d9dde3",lampShade:"#fff1d6"}}function Z_(i){let t=new ie,e=Y_(i.dark),n=At.x1-At.x0,s=At.z1-At.z0;t.add(L(n+.1,.12,s+.1),e.skirt,{y:-.3},"matte",!1),t.add(L(n+.12,.05,.05),e.trim,{y:-.21,z:At.z1+.06},"satin",!1),t.add(L(.05,.05,s+.12),e.trim,{x:At.x1+.06,y:-.21},"satin",!1);let r=.95;t.add(L(n,r,jn+.02),e.wallLow,{y:r/2,z:At.z0-jn/2}),t.add(L(n,At.height-r,jn),e.wall,{y:r+(At.height-r)/2,z:At.z0-jn/2}),t.add(L(jn+.02,r,s+jn),e.wallLow,{x:At.x0-jn/2,y:r/2,z:-jn/2}),t.add(L(jn,At.height-r,s+jn),e.wall,{x:At.x0-jn/2,y:r+(At.height-r)/2,z:-jn/2});for(let[z,X]of[[.06,.12],[r,.04],[At.height-.02,.05]])t.add(L(n,X,.04),e.trim,{y:z,z:At.z0+.02},"satin",!1),t.add(L(.04,X,s),e.trim,{x:At.x0+.02,y:z},"satin",!1);t.add(L(4.7,1.36,.06,.02),e.frame,{y:1.62,z:At.z0+.03},"satin",!1);for(let z of[-1.65,-.55,.55,1.65])t.add(L(1.04,1.14,.02),e.sky,{x:z,y:1.62,z:At.z0+.065},"glow",!1);for(let z of[-1.1,0,1.1])t.add(L(.06,1.16,.05),e.frame,{x:z,y:1.62,z:At.z0+.08},"satin",!1);if(t.add(L(4.6,.04,.05),e.frame,{y:1.62,z:At.z0+.08},"satin",!1),t.add(L(4.9,.05,.16,.015),e.trim,{y:.92,z:At.z0+.08},"satin",!1),i.dark){for(let[z,X]of[[-1.8,1.95],[-.6,1.8],[.5,2],[1.6,1.75],[-1.3,1.45],[.9,1.4],[1.9,2.05],[-.2,2.1]])t.add(L(.03,.03,.01),"#ffffff",{x:z,y:X,z:At.z0+.08},"glow",!1);t.add(Ht(.13,.13,.01,20),"#fff1c4",{x:1.55,y:1.95,z:At.z0+.08,rx:Math.PI/2},"glow",!1)}else for(let[z,X,G]of[[-1.5,1.95,1],[.9,1.75,.8]])for(let[Y,tt,et]of[[0,0,.12],[.13,.02,.09],[-.12,-.01,.08]])t.add(Xn(et*G,10,6),"#ffffff",{x:z+Y*G,y:X+tt*G,z:At.z0+.075,sz:.2},"glow",!1);t.add(L(1,.76,.05,.015),e.woodLight,{x:-4.05,y:1.62,z:At.z0+.03},"satin",!1),t.add(L(.88,.64,.02),"#f3efe7",{x:-4.05,y:1.62,z:At.z0+.06},"matte",!1);for(let[z,X,G,Y,tt]of[[-4.25,1.7,.3,.36,"#e07a5f"],[-3.9,1.52,.4,.22,"#3d405b"],[-3.8,1.78,.18,.18,"#f2cc8f"]])t.add(L(G,Y,.01),tt,{x:z,y:X,z:At.z0+.075},"matte",!1);t.add(Ht(.27,.27,.04,32),"#fbfaf7",{x:3.6,y:1.85,z:At.z0+.04,rx:Math.PI/2},"satin",!1),t.add(cn(.27,.025,Math.PI*2,6,32),"#3b3b40",{x:3.6,y:1.85,z:At.z0+.06},"metal",!1);for(let z=0;z<12;z+=1){let X=z/12*Math.PI*2;t.add(L(.018,z%3===0?.05:.03,.01),"#3b3b40",{x:3.6+Math.sin(X)*.21,y:1.85+Math.cos(X)*.21,z:At.z0+.065,rz:-X},"matte",!1)}for(let z=0;z<bh;z+=1){let{x:X,z:G}=Fr(z),Y=Zi.width+(z===0?.2:0);t.add(L(Y,.045,Zi.depth,.015),e.deskTop,{x:X,y:.645,z:G},"satin");for(let et of[-1,1])t.add(L(.04,.62,Zi.depth-.06,.01),e.deskFrame,{x:X+et*(Y/2-.05),y:.31,z:G},"metal");t.add(L(Y-.14,.28,.02),e.deskFrame,{x:X,y:.46,z:G+Zi.depth/2-.06},"metal"),t.add(L(.22,.014,.14,.006),"#2a2d35",{x:X,y:.674,z:G+.2},"metal"),t.add(L(.04,.2,.03),"#5d6470",{x:X,y:.77,z:G+.22},"metal"),t.add(L(.64,.4,.035,.014),"#1d2027",{x:X,y:1,z:G+.2},"satin"),t.add(L(.38,.018,.13,.006),"#2a2d35",{x:X,y:.676,z:G-.12},"satin"),t.add(L(.34,.006,.1),"#3d414b",{x:X,y:.687,z:G-.12},"matte",!1),t.add(L(.06,.024,.09,.011),"#2a2d35",{x:X+.29,y:.68,z:G-.12},"satin",!1);let tt=z%3;z===0?(t.add(Ht(.07,.08,.02,16),"#2a2d35",{x:X-.55,y:.678,z:G+.15},"metal"),t.add(L(.02,.36,.02),"#5d6470",{x:X-.55,y:.85,z:G+.1,rx:-.35},"metal"),t.add(Xi(.09,.12,16),e.lampShade,{x:X-.55,y:1.02,z:G-.02,rx:Math.PI*.85},i.dark?"glow":"satin",!1)):tt===0?(t.add(Ht(.045,.04,.1,14),"#fbfaf7",{x:X-.38,y:.72,z:G-.05},"satin",!1),t.add(cn(.03,.008,Math.PI*2,6,12),"#fbfaf7",{x:X-.33,y:.72,z:G-.05},"satin",!1)):tt===1?(t.add(Ht(.06,.05,.09,12),e.pot,{x:X-.4,y:.71,z:G+.05},"matte",!1),t.add(qn(.08),e.leafLight,{x:X-.4,y:.81,z:G+.05},"matte",!1)):(t.add(L(.22,.02,.28,.005),["#3d6fa5","#c06c84","#e0a13a"][z%3],{x:X-.36,y:.678,z:G-.05,ry:.2},"matte",!1),t.add(Ht(.008,.008,.16,6),"#1d2027",{x:X-.3,y:.692,z:G-.06,rz:Math.PI/2,ry:.5},"satin",!1)),t.add(L(.46,.07,.44,.03),e.seat,{x:X,y:.29,z:Ai},"matte"),t.add(L(.44,.46,.06,.03),e.chair,{x:X,y:.62,z:Ai-.23,rx:-.08},"matte"),t.add(L(.05,.2,.03),"#3a3f4b",{x:X,y:.4,z:Ai-.22},"metal");for(let et of[-1,1])t.add(L(.04,.12,.04),"#3a3f4b",{x:X+et*.24,y:.37,z:Ai-.02},"metal"),t.add(L(.06,.025,.24,.01),e.chair,{x:X+et*.24,y:.44,z:Ai-.02},"matte");t.add(Ht(.025,.025,.2,10),"#5d6470",{x:X,y:.16,z:Ai},"metal");for(let et=0;et<5;et+=1){let dt=et/5*Math.PI*2;t.add(L(.04,.025,.24),"#3a3f4b",{x:X+Math.sin(dt)*.12,y:.05,z:Ai+Math.cos(dt)*.12,ry:dt},"metal",!1),t.add(Xn(.025,8,6),"#1d2027",{x:X+Math.sin(dt)*.24,y:.025,z:Ai+Math.cos(dt)*.24},"satin",!1)}}let a=2,o=(sn.x0+sn.x1)/2,l=(sn.z0+sn.z1)/2,c=sn.x1-sn.x0,h=sn.z1-sn.z0;for(let z of[sn.z0,sn.z1])t.add(L(c,a,.05,.01),e.wood,{x:o,y:a/2,z},"satin");t.add(L(.03,a,h),e.woodLight,{x:sn.x0+.02,y:a/2,z:l},"matte",!1);let p=["#b5523b","#3d6fa5","#e0a13a","#4f8a5b","#7b5ea7","#c06c84","#2f4858","#d9c5a0"];for(let z=0;z<5;z+=1){let X=.04+z*.48;if(t.add(L(c,.035,h,.008),e.wood,{x:o,y:X,z:l},"satin"),z===4)break;let G=sn.z0+.08,Y=z*3;for(;G<sn.z1-.14;){let tt=.06+Y*37%5*.012,et=.26+Y*13%4*.035,dt=Y%9===4?.22:0;t.add(L(.22,et,tt,.006),p[Y%p.length],{x:sn.x0+.17,y:X+.02+et/2,z:G+tt/2+dt*.3,rx:dt},"matte",!1),G+=tt+.01+dt*.4,Y+=1}}t.add(Ht(.06,.08,.2,14),"#e8e2d8",{x:o,y:a+.12,z:sn.z0+.35},"satin",!1),t.add(qn(.09),e.leaf,{x:o,y:a+.27,z:sn.z0+.35},"matte",!1);let d=(Zn.z0+Zn.z1)/2,f=Zn.z1-Zn.z0;t.add(L(.04,1.08,f+.08,.012),"#aeb5bf",{x:Zn.x,y:1.45,z:d},"metal"),t.add(L(.02,1,f),"#fcfcfa",{x:Zn.x+.025,y:1.45,z:d},"satin",!1),t.add(L(.08,.025,f,.008),"#aeb5bf",{x:Zn.x+.06,y:.93,z:d},"metal",!1);for(let[z,X]of[[-.3,"#d1495b"],[-.18,"#3f88c5"],[.1,"#2a9d8f"]])t.add(Ht(.012,.012,.12,8),X,{x:Zn.x+.07,y:.955,z:d+z,rx:Math.PI/2},"satin",!1);t.add(Ht(1.32,1.32,.015,48),e.rug,{x:Se.x,y:.008,z:Se.z},"matte",!1),t.add(cn(1.25,.02,Math.PI*2,4,48),i.dark?"#4a4057":"#c9b8d3",{x:Se.x,y:.016,z:Se.z,rx:Math.PI/2},"matte",!1),t.add(Ht(Se.radius,Se.radius,.05,40),e.deskTop,{x:Se.x,y:.61,z:Se.z},"satin"),t.add(Ht(Se.radius-.02,Se.radius-.08,.04,40),e.deskFrame,{x:Se.x,y:.57,z:Se.z},"metal",!1),t.add(Ht(.06,.06,.52,14),"#5d6470",{x:Se.x,y:.31,z:Se.z},"metal"),t.add(Ht(.32,.36,.04,28),"#3a3f4b",{x:Se.x,y:.03,z:Se.z},"metal");for(let z of Or)t.add(Ht(.2,.2,.07,20),e.seat,{x:z.x,y:.29,z:z.z},"matte"),t.add(Ht(.025,.025,.24,8),"#5d6470",{x:z.x,y:.14,z:z.z},"metal",!1),t.add(Ht(.15,.17,.025,18),"#3a3f4b",{x:z.x,y:.013,z:z.z},"metal",!1);let _=(rn.x0+rn.x1)/2,b=(rn.z0+rn.z1)/2;t.add(L(rn.x1-rn.x0,2,rn.z1-rn.z0,.02),"#23262e",{x:_,y:1,z:b},"satin"),t.add(L(.02,1.86,rn.z1-rn.z0-.08),"#30343e",{x:rn.x0-.002,y:1,z:b},"satin",!1);for(let z=0;z<7;z+=1)t.add(L(.012,.012,rn.z1-rn.z0-.16),"#16181d",{x:rn.x0-.012,y:.3+z*.22,z:b},"matte",!1);let m=(an.x0+an.x1)/2,u=(an.z0+an.z1)/2;t.add(L(an.x1-an.x0,.05,an.z1-an.z0,.012),"#5d6470",{x:m,y:.9,z:u},"metal"),t.add(L(.06,.88,.06),"#3a3f4b",{x:m,y:.44,z:u},"metal"),t.add(L(.4,.03,.5,.01),"#3a3f4b",{x:m,y:.015,z:u},"metal",!1);for(let z of[-2.75,-2.05]){t.add(L(.04,.42,.62,.012),"#1d2027",{x:an.x1-.12,y:1.2,z},"satin"),t.add(L(.01,.34,.54),i.dark?"#1f6f5a":"#2f8f74",{x:an.x1-.145,y:1.2,z},"glow",!1);for(let X=0;X<4;X+=1)t.add(L(.004,.02,.18+X%2*.14),"#8af0c8",{x:an.x1-.152,y:1.3-X*.07,z:z-.12+X%2*.07},"glow",!1)}let S=(qe.x0+qe.x1)/2,R=(qe.z0+qe.z1)/2,v=qe.z1-qe.z0;t.add(L(1.9,.012,2.5,.004),e.rugLounge,{x:-4.6,y:.007,z:R},"matte",!1),t.add(L(qe.x1-qe.x0,.2,v,.05),e.sofa,{x:S,y:.14,z:R}),t.add(L(.2,.55,v,.06),e.sofa,{x:qe.x0+.1,y:.42,z:R});for(let z of[qe.z0+.08,qe.z1-.08])t.add(L(qe.x1-qe.x0,.36,.16,.06),e.sofa,{x:S,y:.3,z});for(let z of[R-v/4+.04,R+v/4-.04])t.add(L(qe.x1-qe.x0-.24,.09,v/2-.14,.04),e.cushion,{x:S+.1,y:.29,z}),t.add(L(.14,.34,v/2-.16,.05),e.cushion,{x:qe.x0+.26,y:.52,z,rz:-.18});t.add(L(.1,.22,.22,.05),i.accent,{x:qe.x0+.36,y:.45,z:qe.z1-.32,rz:-.25,ry:.3},"matte"),t.add(Ht(.14,.16,.025,18),"#2a2d35",{x:-5.62,y:.013,z:4.28},"metal",!1),t.add(Ht(.015,.015,1.5,8),"#5d6470",{x:-5.62,y:.76,z:4.28},"metal"),t.add(Ht(.14,.2,.26,20),e.lampShade,{x:-5.62,y:1.58,z:4.28},i.dark?"glow":"satin",!1);let M=(Rn.x0+Rn.x1)/2,E=(Rn.z0+Rn.z1)/2,A=Rn.x1-Rn.x0;t.add(L(A,.84,Rn.z1-Rn.z0,.02),e.counter,{x:M,y:.42,z:E});for(let z of[-A/4,A/4])t.add(L(A/2-.06,.72,.01),e.woodLight,{x:M+z,y:.44,z:Rn.z0-.003},"satin",!1),t.add(L(.1,.015,.02),"#aeb5bf",{x:M+z,y:.7,z:Rn.z0-.015},"metal",!1);t.add(L(A+.06,.04,Rn.z1-Rn.z0+.06,.012),e.top,{x:M,y:.86,z:E},"satin"),t.add(L(.3,.36,.26,.03),"#2b2e36",{x:M-.25,y:1.06,z:E},"metal"),t.add(L(.22,.02,.12,.006),"#5d6470",{x:M-.25,y:.89,z:E-.08},"metal",!1),t.add(L(.04,.04,.01),"#ff6b4a",{x:M-.25,y:1.16,z:E-.135},"glow",!1);for(let z of[.18,.32])t.add(Ht(.045,.04,.1,14),"#fbfaf7",{x:M+z,y:.93,z:E},"satin",!1);t.add(L(.36,.8,.36,.04),e.cooler,{x:On.x,y:.4,z:On.z},"satin"),t.add(L(.08,.05,.05),"#3f88c5",{x:On.x-.19,y:.62,z:On.z},"satin",!1),t.add(Ht(.15,.15,.4,20),"#8fc9ff",{x:On.x,y:1,z:On.z},"glass",!1),t.add(Ht(.05,.05,.05,12),"#3f88c5",{x:On.x,y:1.22,z:On.z},"satin",!1);let g=(Ve.z0+Ve.z1)/2;for(let z of[Ve.z0,Ve.z1])t.add(L(.14,2.2,.1,.02),e.woodLight,{x:Ve.x+.04,y:1.1,z},"satin");t.add(L(.16,.14,Ve.z1-Ve.z0+.1,.02),e.woodLight,{x:Ve.x+.04,y:2.2,z:g},"satin"),t.add(L(.55,.012,.95,.004),e.rugLounge,{x:Ve.x-.4,y:.007,z:g},"matte",!1);let w=2.2,T=i.dark?"#7fb6d6":"#cfe8f4",I=i.dark?"#8a93a3":"#aeb5bf",N=le.z-At.z0;t.add(L(.025,w,N),T,{x:le.x,y:w/2,z:At.z0+N/2},"glass",!1);for(let[z,X]of[[le.x,le.door.x0],[le.door.x1,an.x0]])t.add(L(X-z,w,.025),T,{x:(z+X)/2,y:w/2,z:le.z},"glass",!1);for(let z of[.02,w])t.add(L(.05,.04,N),I,{x:le.x,y:z,z:At.z0+N/2},"metal",!1),t.add(L(an.x0-le.x,.04,.05),I,{x:(le.x+an.x0)/2,y:z,z:le.z},"metal",!1);for(let z of[At.z0+.7,At.z0+1.4,le.z])t.add(L(.05,w,.05),I,{x:le.x,y:w/2,z},"metal",!1);for(let z of[le.door.x0,le.door.x1])t.add(L(.04,w,.05),I,{x:z,y:w/2,z:le.z},"metal",!1);let B=(mn.x0+mn.x1)/2,F=(mn.z0+mn.z1)/2,P=mn.x1-mn.x0,V=mn.z1-mn.z0;t.add(L(P,.55,V,.02),e.wood,{x:B,y:.275,z:F},"satin"),t.add(L(P-.08,.004,.01),e.woodLight,{x:B,y:.3,z:mn.z1+.002},"matte",!1),t.add(L(P-.1,.24,V-.06,.03),i.dark?"#c9ccd2":"#eef0f3",{x:B,y:.67,z:F-.02},"satin"),t.add(L(P-.16,.04,V-.14,.012),"#3a3f4b",{x:B,y:.81,z:F-.04},"satin",!1),t.add(L(.3,.012,.16,.004),"#5d6470",{x:B,y:.6,z:mn.z1+.04,rx:.12},"satin",!1),t.add(L(.03,.03,.01),"#38d39f",{x:B+.22,y:.74,z:mn.z1-.03},"glow",!1);for(let[z,X]of Mh.entries()){t.add(Ht(.21,.15,.38,18),e.pot,{x:X.x,y:.19,z:X.z},"satin"),t.add(cn(.205,.02,Math.PI*2,6,18),e.pot,{x:X.x,y:.38,z:X.z,rx:Math.PI/2},"satin",!1),t.add(Ht(.19,.19,.02,16),e.soil,{x:X.x,y:.36,z:X.z},"matte",!1);let G=z%2===1;G&&t.add(Ht(.02,.025,.7,6),"#5b4636",{x:X.x,y:.7,z:X.z},"matte");let Y=G?1.05:.58,tt=[[0,0,0,.3,e.leaf],[.14,.12,.05,.2,e.leafLight],[-.12,.16,-.06,.18,e.leafLight],[.02,.3,.02,.17,e.leaf],[-.05,.06,.15,.16,e.leafLight]];for(let[et,dt,Dt,Pt,xt]of tt)t.add(qn(Pt*(G?.9:1)),xt,{x:X.x+et,y:Y+dt,z:X.z+Dt,ry:et*7},"matte")}return t}function sf(i,t){let e=Z_(i).build(),n=q_(i.dark),s=At.x1-At.x0,r=At.z1-At.z0,a=new de(s,.24,r);a.translate(0,-.12,0);let o=new Ae({map:n,roughness:.82}),l=["#38d39f","#4aa3ff","#f2c230"],c=[new ie,new ie];for(let A=0;A<7;A+=1)for(let g=0;g<3;g+=1)c[(A+g)%2].add(L(.012,.035,.06),l[g],{x:rn.x0-.016,y:.36+A*.22,z:rn.z0+.2+g*.25},"glow",!1);let h=c.map(A=>A.build()[0].geometry),p=L(.03,.14,.01).clone().translate(0,.06,0),d=L(.02,.21,.01).clone().translate(0,.095,0),f=new Ae({color:"#25252a",roughness:.5}),_=new ie;for(let A=0;A<3;A+=1)_.add(L(.21,.006,.28),"#fbfaf6",{y:A*.007,ry:(A-1)*.07});let b=_.build()[0].geometry,m=le.door.x1-le.door.x0,u=new ie;u.add(L(m-.04,2.1,.02),i.dark?"#7fb6d6":"#cfe8f4",{y:1.07},"glass",!1);for(let A of[-m/2+.02,m/2-.02])u.add(L(.035,2.12,.035),i.dark?"#8a93a3":"#aeb5bf",{x:A,y:1.07},"metal",!1);u.add(L(.02,.32,.04,.008),"#5d6470",{x:m/2-.09,y:1.05,z:.03},"metal",!1);let S=u.build(),R=new de(an.x0-le.x,.025,.03),v=Ve.z1-Ve.z0-.12,M=new ie;M.add(L(.05,2.06,v,.015),i.dark?"#5f4836":"#bf9468",{y:1.04,z:v/2},"satin"),M.add(L(.06,.6,v-.3,.01),i.dark?"#4e3b2c":"#a5784f",{y:1.5,z:v/2},"satin",!1),M.add(L(.1,.03,.12,.01),"#aeb5bf",{y:1,z:v-.12},"metal",!1);let E=M.build();return{theme:i,finishes:t,furniture:e,floor:{geometry:a,material:o,texture:n},leds:h,hands:{hour:p,minute:d,material:f},printout:b,sandbox:{door:S,strip:R},entrance:E,dispose(){for(let A of e)A.geometry.dispose();for(let A of E)A.geometry.dispose();for(let A of S)A.geometry.dispose();R.dispose(),a.dispose(),o.dispose(),n.dispose();for(let A of h)A.dispose();p.dispose(),d.dispose(),f.dispose(),b.dispose()}}}function rf(i){let{theme:t,finishes:e}=i,n=new ae;for(let M of Ei(i.furniture,e))n.add(M);let s=new Xt(i.floor.geometry,i.floor.material);s.receiveShadow=!0,s.matrixAutoUpdate=!1,n.add(s);let r=[],a=[];for(let M=0;M<bh;M+=1){let{x:E,z:A}=Fr(M),g=new Ae({color:"#0e1420",emissive:"#203048",emissiveIntensity:.35,roughness:.3});a.push(g),r.push(g);let w=new Xt(W_,g);w.position.set(E,1,A+.18),n.add(w)}let o=new ae;o.position.set(Zn.x+.04,1.45,(Zn.z0+Zn.z1)/2),n.add(o);let l=new Ae({color:t.accent,emissive:t.accent,emissiveIntensity:1.4,transparent:!0,opacity:.85});r.push(l);let c=new Xt(X_,l);c.position.set(Se.x,.95,Se.z),c.rotation.x=Math.PI/2,c.visible=!1,n.add(c);let h=i.leds.map(M=>{let E=new Te({vertexColors:!0,toneMapped:!1});return r.push(E),n.add(new Xt(M,E)),E}),p=new Xt(i.hands.hour,i.hands.material),d=new Xt(i.hands.minute,i.hands.material);p.position.set(3.6,1.85,At.z0+.08),d.position.set(3.6,1.85,At.z0+.09),n.add(p,d);let f=Fr(0),_=new yi("#ffc978",0,3.2,1.6);_.position.set(f.x-.5,.98,f.z-.05),_.visible=!1,n.add(_);let b=new Xt(i.printout,e.matte);b.position.set((mn.x0+mn.x1)/2,.615,mn.z1+.05),b.rotation.x=.12,b.visible=!1,n.add(b);let m=new ae;for(let M of Ei(i.sandbox.door,e))m.add(M);m.position.set((le.door.x0+le.door.x1)/2,0,le.z+.045),n.add(m);let u=new Te({color:t.dark?"#3a4558":"#c4ccd6",toneMapped:!1});r.push(u);let S=new Xt(i.sandbox.strip,u);S.position.set((le.x+an.x0)/2,2.25,le.z),n.add(S);let R=new ae;for(let M of Ei(i.entrance,e))R.add(M);R.position.set(Ve.x+.04,0,Ve.z0+.06),n.add(R);let v=[];if(t.dark)for(let[M,E,A]of[[0,2.1,-1.8],[-5.3,1.6,4],[1.6,2,1.5]]){let g=new yi("#ffcf8a",9,9,1.4);g.position.set(M,E,A),n.add(g),v.push(g)}return{group:n,screens:a,notes:o,ring:c,leds:h,clock:{hour:p,minute:d},lamps:v,deskLamp:_,printout:b,sandbox:{door:m,strip:u},entrance:R,dispose(){n.removeFromParent();for(let M of o.children)M.material.dispose();for(let M of r)M.dispose();for(let M of v)M.dispose();_.dispose()}}}function Uh(i,t,e){let n=[...i.querySelectorAll(".studio-tag, .studio-floor-sign")];for(let s=n.length-1;s>=0;s--){let r=n[s],a=r.getBoundingClientRect();if(!a.width||t<a.left||t>a.right||e<a.top||e>a.bottom)continue;let o=getComputedStyle(r);if(o.visibility!=="hidden"&&Number(o.opacity)>=.1)return r}return null}var qs=new O(-.3,.5,.2),ql={polar:.98,azimuth:.62},Ba={polar:1.16,azimuth:.72},Yl=7.1,Pi=At.height+.4,Wr=1.2,Lh=-.87,$_=1.75,Zl=16,K_=7,$l=1.35,af=1e3/30,of=20,Dh={x:Br.x,z:Br.z},zh={x:Ve.x,z:(Ve.z0+Ve.z1)/2},J_=1.5,j_=1.35,Nh=new O(-5,11,8),Q_=L(.01,.2,.22,.004),lf={x:(le.door.x0+le.door.x1)/2,z:le.z},ty=14,ey=1.6,ny=1e3/12,iy=4e3,sy=.75,ry=1e3/30,ay=1e3,Kl={polar:1.02,azimuth:.5},Xr=class{constructor(t){re(this,"from");re(this,"to");re(this,"start",0);re(this,"seconds",0);this.from=t,this.to=t}get target(){return this.to}set(t,e,n){t!==this.to&&(this.from=this.value(e),this.to=t,this.start=e,this.seconds=n)}value(t){return this.seconds<=0?this.to:this.from+(this.to-this.from)*cf(Math.min(1,(t-this.start)/this.seconds))}done(t){return this.seconds<=0||t-this.start>=this.seconds}};function cf(i){return i<.5?4*i*i*i:1-(-2*i+2)**3/2}function Ss(i){return`${i.x.toFixed(2)},${i.z.toFixed(2)}`}function oy(i,t){let{actor:e}=i;return i.errand?i.errand.phase==="carry"?"carry":"operate":e.state==="waiting"?"raise":e.state==="failed"?"slump":e.state==="answering"?"type":e.state==="working"?e.spot==="shelf"?"read":e.spot==="terminal"||e.spot==="sandbox"?"operate":e.spot==="board"?"write":e.spot==="table"?"talk":e.spot==="window"?"gaze":e.activity==="search"?"browse":e.activity==="read"?"paper":e.activity==="thinking"?"think":"type":kl.includes(t)?"gaze":t===Na[0]||t.x===Na[1].x&&t.z===Na[1].z?"sip":"rest"}function hf(i,t,e,n,s="room"){let r=s,a=()=>r==="backdrop"?sy:Math.min(window.devicePixelRatio||1,1.25),o=new Dr({antialias:!0,alpha:!0,powerPreference:"low-power"});o.setPixelRatio(a()),o.shadowMap.enabled=!0,o.shadowMap.type=Gi,o.shadowMap.autoUpdate=!1,o.outputColorSpace=He,o.toneMapping=Bs,o.toneMappingExposure=e.dark?1.05:1,o.domElement.classList.add("studio-canvas"),o.domElement.setAttribute("aria-hidden","true"),i.prepend(o.domElement);let l=new Ds,c=new Ye(30,1,.5,160),h=new Vr(c,o.domElement);h.target.copy(qs),h.enableDamping=!0,h.dampingFactor=.08,h.enablePan=!1,h.rotateSpeed=.6,h.zoomSpeed=.8,h.enabled=r==="room",i.dataset.mode=r,l.add(new Us(e.dark?"#9fb0e0":"#fff6ea",e.dark?"#3a3040":"#b8a48c",e.dark?1.35:1.5));let p=new Vi(e.dark?"#b9c8ff":"#fff1dc",e.dark?1.5:2.2);p.castShadow=!0,p.shadow.mapSize.set(1024,1024),p.shadow.camera.near=1,p.shadow.bias=-6e-4,p.shadow.radius=3,l.add(p,p.target);let d=new Vi(e.dark?"#5b4b8a":"#cfe3ff",e.dark?.35:.6);d.position.set(9,5,-3),l.add(d);let f=Ul(),_=sf({dark:e.dark,accent:e.accent},f),b=e.dark?"#3b4252":"#d8d2c8",m=At.x1-At.x0,u=At.z1-At.z0,S=new ie;for(let[Z,Q]of[[At.x1+.13,At.z1+.13],[At.x1+.13,At.z0-.05],[At.x0-.05,At.z1+.13]])S.add(L(.26,At.height,.26,.03),b,{x:Z,y:At.height/2,z:Q},"satin"),S.add(L(.3,.06,.3,.01),e.dark?"#4a5263":"#e6e0d6",{x:Z,y:At.height-.03,z:Q},"satin",!1);let R=S.build(),v=new ie;v.add(L(m+.5,.36,u+.5),e.dark?"#2b2f38":"#e9e4dc",{y:-.18},"matte",!1),v.add(L(m+.3,.02,u+.3),e.dark?"#353a45":"#d9d3c8",{y:.01},"matte",!1);for(let[Z,Q,ht,St]of[[m+.5,.14,0,At.z0-.18],[m+.5,.14,0,At.z1+.18],[.14,u+.5,At.x0-.18,0],[.14,u+.5,At.x1+.18,0]])v.add(L(Z,.42,Q,.02),b,{x:ht,y:.21,z:St},"satin");v.add(L(1.6,.6,1.1,.04),e.dark?"#4d5466":"#c9c3b8",{x:-3.2,y:.3,z:-2.6},"satin");for(let Z of[-.45,0,.45])v.add(Ht(.17,.17,.04,16),"#2a2d35",{x:-3.2+Z,y:.62,z:-2.6},"metal",!1);for(let Z=0;Z<2;Z+=1)for(let Q=0;Q<3;Q+=1){let ht=.4+Q*1.25,St=.6+Z*1.15;v.add(L(1.1,.04,.9,.01),e.dark?"#1c2a4a":"#2c4a7a",{x:ht,y:.42,z:St,rx:-.3},"satin"),v.add(L(.04,.32,.04),"#8a919c",{x:ht,y:.18,z:St-.3},"metal",!1)}v.add(Ht(.04,.05,1.6,8),b,{x:4.2,y:.8,z:-3.4},"metal"),v.add(Xn(.09,10,8),"#ff3b30",{x:4.2,y:1.65,z:-3.4},"glow",!1);let M=new ae;for(let Z of Ei(v.build(),f))M.add(Z);let E=new Xr(0),A=!1,g=new ie;g.add(L(m+2*Wr,.5,u+2*Wr,.04),e.dark?"#262a33":"#cfc8bc",{y:Lh+.25},"matte",!1),g.add(L(m+2.2,.03,u+2.2),e.dark?"#2f4a3a":"#9cc49a",{y:-.36},"matte",!1),g.add(L(1.6,.035,1.1),e.dark?"#3a3f4b":"#e6e0d6",{x:4.4,y:-.355,z:At.z1+.7},"matte",!1);for(let[Z,Q]of[[-6.6,5.2],[6.6,5.2],[-6.6,-5],[6.7,-1]])g.add(qn(.4),"#4f8a5b",{x:Z,y:-.1,z:Q},"matte"),g.add(qn(.26),"#6aa86f",{x:Z+.2,y:.1,z:Q-.1},"matte");let w=new ae;for(let Z of Ei(g.build(),f))w.add(Z);l.add(M,w);let T=document.createElement("canvas");T.width=T.height=128;let I=T.getContext("2d");if(I){let Z=I.createRadialGradient(64,64,0,64,64,64);Z.addColorStop(0,e.dark?"rgba(0, 0, 0, 0.55)":"rgba(38, 48, 78, 0.28)"),Z.addColorStop(.5,e.dark?"rgba(0, 0, 0, 0.25)":"rgba(38, 48, 78, 0.12)"),Z.addColorStop(1,"rgba(0, 0, 0, 0)"),I.fillStyle=Z,I.fillRect(0,0,128,128)}let N=new Hi(T);N.colorSpace=He;let B=new Xt(new Ns(m+9,u+9),new Te({map:N,transparent:!0,depthWrite:!1,toneMapped:!1}));B.rotation.x=-Math.PI/2,B.position.y=-.26,B.renderOrder=-1,l.add(B);let F=new $n(Xd()),P=new Map,V=[],z=e.reducedMotion,X=!1,G=!1,Y=null,tt=null,et="",dt="",Dt="",Pt=!1,xt=null,q=()=>V.length>=2,it=()=>Y===null?void 0:P.get(Y),gt=()=>q()&&Y===null,zt=Z=>{let Q=en.degToRad(c.fov)/2,ht=Math.atan(Math.tan(Q)*c.aspect);return Z/Math.sin(Math.min(Q,ht))},Rt=(Z,Q,ht,St,Et)=>{let It=new O().setFromSpherical(new Tn(1,Q,ht)),Ut=new O(0,1,0).cross(It).normalize(),y=It.clone().cross(Ut),D=Math.tan(en.degToRad(c.fov)/2),k=D*c.aspect,H=new O,$=0;for(let mt=0;mt<8;mt+=1){H.set(mt&1?Et.x:St.x,mt&2?Et.y:St.y,mt&4?Et.z:St.z).sub(Z);let Ct=H.dot(It);$=Math.max($,Ct+Math.abs(H.dot(Ut))/k,Ct+Math.abs(H.dot(y))/D)}return $},Yt=()=>V.length*Pi+.6,Me=()=>{let Z=V[0],Q=Z?.members.get("lead"),ht=Q?.person.position??za(0),St=Q!==void 0&&Q.actor.state!=="idle"&&Q.actor.state!=="done"&&Q.actor.state!=="stopped",Et=new O(Math.cos(Kl.azimuth),0,-Math.sin(Kl.azimuth)),It=c.aspect<1,Ut=Z!==void 0&&[...Z.members.values()].some(k=>!k.actor.lead&&(k.actor.state==="working"||k.actor.state==="arriving"||k.actor.state==="waiting")),y=(k,H)=>{if(!It)return k;let $=k.radius*Math.tan(en.degToRad(c.fov)/2);return{...k,target:k.target.clone().setY(k.target.y-2*H*$/Math.sin(k.polar))}};if(Ut)return y({target:qs.clone().addScaledVector(Et,It?0:-.9),radius:zt(Yl)*.52,...Kl},.08);let D=qs.clone().lerp(new O(ht.x,.75,ht.z),It?.85:.7).addScaledVector(Et,It?0:-1.1);return y({target:D,radius:zt(Yl)*(St?.31:.38),...Kl},.18)},Qt=()=>{if(r==="backdrop")return Me();if(gt()){let ht=Yt(),St=new O(Math.cos(Ba.azimuth),0,-Math.sin(Ba.azimuth)).multiplyScalar(Yl*.3),Et=new O(qs.x,ht/2-.5,qs.z).add(St),It=new O(At.x0-Wr,Lh,At.z0-Wr),Ut=new O(At.x1+Wr,V.length*Pi+$_,At.z1+Wr);return{target:Et,radius:Rt(Et,Ba.polar,Ba.azimuth,It,Ut)*1.04,...Ba}}let Z=it()?.index??0,Q=qs.clone().setY(qs.y+Z*Pi);if(c.aspect<1){let ht=Z*Pi,St=new O(At.x0,ht,At.z0),Et=new O(At.x1,ht+At.height,At.z1);return{target:Q,radius:Rt(Q,ql.polar,ql.azimuth,St,Et)*1.02,...ql}}return{target:Q,radius:zt(Yl),...ql}},ne=()=>{let Z=new Tn().setFromVector3(c.position.clone().sub(h.target));return{target:h.target.clone(),radius:Z.radius,polar:Z.phi,azimuth:Z.theta}},Kt=Z=>{h.target.copy(Z.target),c.position.setFromSpherical(new Tn(Z.radius,Z.polar,Z.azimuth)).add(Z.target),c.lookAt(Z.target)},te=()=>{let Z=Qt();h.minDistance=Z.radius*.45,h.maxDistance=Z.radius*1.5,h.minPolarAngle=.35,h.maxPolarAngle=gt()?1.45:1.28,h.minAzimuthAngle=-.4,h.maxAzimuthAngle=1.5},xe=Z=>{let Q=Qt();if(!Z||z||!Pt){tt=null,h.enabled=r==="room",Kt(Q),te(),h.update();return}tt={from:ne(),to:Q,start:performance.now()/1e3},h.enabled=!1},ze=Z=>{if(!tt)return;let Q=cf(Math.min(1,(Z-tt.start)/$l)),{from:ht,to:St}=tt,Et=Math.sin(Q*Math.PI)*(gt()?.04:.08);Kt({target:ht.target.clone().lerp(St.target,Q),radius:en.lerp(ht.radius,St.radius,Q)*(1+Et),polar:en.lerp(ht.polar,St.polar,Q),azimuth:en.lerp(ht.azimuth,St.azimuth,Q)}),Z-tt.start>=$l&&(tt=null,h.enabled=r==="room",Kt(St),te(),h.update())},Ne=(Z,Q=!1)=>{let ht=z||Q?0:$l,St=it();for(let Ut of V){let y=q()&&St!==void 0&&Ut.index>St.index;Ut.y.set(Ut.index*Pi+(y?Zl:0),Z,ht)}let Et=V.length*Pi;q()?A||(A=!0,E=new Xr(Et+Zl)):A=!1,E.set(Et+(q()&&St!==void 0?Zl:0),Z,ht);let It=gt()?`building|${V.length}`:`floor|${St?.index??0}`;It!==dt&&(dt=It,xe(!Q))},ge=Z=>{let{actor:Q,tag:ht,bubble:St}=Z;ht.dataset.state=Q.state,ht.dataset.lead=Q.lead?"true":"false",ht.querySelector(".studio-tag-name").textContent=Q.name,ht.querySelector(".studio-tag-state").textContent=Q.stateLabel,ht.setAttribute("aria-label",`${Q.name}: ${Q.stateLabel}`),Z.tagSize=null,St.textContent=Q.bubble??"",St.hidden=!Q.bubble,St.dataset.state=Q.state},Ee=Z=>{let{view:Q}=Z;Z.sign.dataset.busy=Q.busy?"true":"false",Z.sign.querySelector(".studio-floor-number").textContent=Q.number,Z.sign.querySelector(".studio-floor-title").textContent=Q.title,Z.sign.querySelector(".studio-floor-summary").textContent=Q.summary,Z.sign.setAttribute("aria-label",`${Q.number} ${Q.title}: ${Q.summary}`),Z.signWidth=Z.sign.offsetWidth},W=(Z,Q,ht,St)=>{let Et=za(ht),It=!!Q.leaves&&Q.state!=="working"&&Q.state!=="arriving"&&Q.state!=="waiting"&&Q.state!=="answering",Ut=new Gr(Q.id,Q.look,Z.first&&!It?Et:Dh,e.accent,f);Z.first&&!It&&(Ut.heading=Math.atan2(Et.face.x-Et.x,Et.face.z-Et.z)),Ut.root.visible=!It,Z.group.add(Ut.root);let y=document.createElement("button");y.type="button",y.className="studio-tag",y.tabIndex=-1;let D=document.createElement("span");D.className="studio-tag-dot";let k=document.createElement("span");k.className="studio-tag-name";let H=document.createElement("span");H.className="studio-tag-state",y.append(D,k,H),y.addEventListener("click",()=>n.pick(Z.id,Q.id));let $=document.createElement("div");$.className="studio-bubble",t.append($,y);let mt={person:Ut,actor:Q,desk:ht,tag:y,bubble:$,since:St,idleNext:St+4+Math.random()*6,idlePlace:null,spotSince:St,errands:new Set(Q.errand?[Q.errand]:[]),errand:null,gone:It,enters:0,key:It?Ss(Br):"",tagSize:null};return ge(mt),mt},Pe=Z=>{Z.person.dispose(),Z.tag.remove(),Z.bubble.remove()},_e=(Z,Q)=>{let ht=new ae;ht.userData.floorId=Z.id;let St=rf(_);ht.add(St.group);let Et=new ae;for(let y of Ei(R,f))Et.add(y);ht.add(Et);let It=document.createElement("button");It.type="button",It.className="studio-floor-sign",It.tabIndex=-1;for(let y of["studio-floor-number","studio-floor-title","studio-floor-summary"]){let D=document.createElement("span");D.className=y,It.append(D)}It.addEventListener("click",()=>n.pickFloor(Z.id)),It.style.visibility="hidden",t.append(It);let Ut={id:Z.id,index:Q,view:Z,group:ht,room:St,posts:Et,members:new Map,first:!0,notesSignature:"",y:new Xr(Q*Pi),sign:It,signWidth:0};return ht.position.y=Q*Pi,l.add(ht),Ut},C=Z=>{for(let Q of Z.members.values())Pe(Q);Z.members.clear(),Z.room.dispose(),Z.group.removeFromParent(),Z.sign.remove()},x=(Z,Q,ht)=>{let St=new Set(Q.map(Ut=>Ut.id));for(let[Ut,y]of Z.members)St.has(Ut)||(Pe(y),Z.members.delete(Ut));let Et=1,It=0;for(let Ut of Q){let y=Ut.lead?0:Et++,D=Z.members.get(Ut.id);if(!D){let k=W(Z,Ut,y,ht);!Z.first&&!k.gone&&(k.enters=ht+J_*It++),Z.members.set(Ut.id,k);continue}D.actor.state!==Ut.state&&(D.since=ht,Ut.state==="done"&&D.person.cheer(ht)),D.actor.spot!==Ut.spot&&(D.spotSince=ht),D.actor=Ut,D.desk=y,ge(D)}Z.first=!1},K=Z=>{let Q=performance.now()/1e3,ht=P.size===0,St=new Set(Z.map(D=>D.id));for(let[D,k]of P)St.has(D)||(C(k),P.delete(D));let Et=[],It=[];Z.forEach((D,k)=>{let H=P.get(D.id);H||(H=_e(D,k),P.set(D.id,H),It.push(H)),H.index=k,H.view=D,Ee(H),x(H,D.cast,Q),Et.push(H)});let Ut=q();V=Et,q()?(!Ut||Y!==null&&!P.has(Y))&&(Y=null):Y=V[0]?.id??null;let y=it();for(let D of It){let k=q()&&y!==void 0&&D.index>y.index,H=D.index*Pi+(k?Zl:0);D.y=new Xr(H+(gt()&&!ht&&!z?K_:0)),D.y.set(H,Q,$l),D.group.position.y=D.y.value(Q)}Ne(Q,ht)},j=(Z,Q)=>{let ht=new Map,St=(Et,It)=>{for(let Ut of Et){let y=Ss(Ut);if(!ht.has(y))return ht.set(y,1),Ut}return It};for(let Et of Z.members.values()){let{actor:It,person:Ut}=Et,y=za(Et.desk),D=It.state==="idle"||It.state==="stopped"||It.state==="done"&&Q-Et.since>of;It.errand&&!Et.errands.has(It.errand)&&(Et.errands.add(It.errand),z||(Et.errand={phase:"fetch",at:null})),Et.errand&&(D||It.state==="waiting"||It.state==="failed")&&(Et.errand=null);let k=!!It.leaves&&(D||It.state==="failed"&&Q-Et.since>of);!k&&Et.gone&&(Et.gone=!1,Ut.root.visible=!0);let H;if(k)H=Br,Et.key===Ss(Br)&&!Ut.walking&&!Et.gone&&(Et.gone=!0,Ut.root.visible=!1);else if(Et.errand){let mt=Et.errand,Ct=wt=>Et.key===Ss(wt)&&!Ut.walking;mt.phase==="fetch"&&Ct(Sh)?(mt.at??(mt.at=Q),Q-mt.at>ey&&(mt.phase="carry")):mt.phase==="carry"&&Ct(y)&&(Et.errand=null),H=Et.errand?.phase==="fetch"?Sh:y}else if(D){if(!z&&r==="room"&&Q>Et.idleNext&&!Ut.walking){let mt=[y,...Na].filter(Ct=>Ct===y||!ht.has(Ss(Ct)));Et.idlePlace=mt[Math.floor(Math.random()*mt.length)]??y,Et.idleNext=Q+(It.lead?22:12)+Math.random()*16}H=Et.idlePlace??y}else Et.idlePlace=null,Et.idleNext=Q+6,H=It.spot==="shelf"?St(kd,y):It.spot==="terminal"?St(Vd,y):It.spot==="sandbox"?St(Gd,y):It.spot==="door"?St([Wd],y):It.spot==="table"?St(It.lead?[Or[3],...Or]:Or,y):It.spot==="board"?St([Hd],y):It.spot==="window"?kl[Q-Et.spotSince>ty&&!z?Math.floor((Q-Et.spotSince)/7)%2:0]:y;Q<Et.enters&&(H={x:Dh.x,z:Dh.z,face:zh,sit:!1}),ht.set(Ss(H),1);let $=Ss(H);$!==Et.key&&(Et.key=$,Ut.goTo(H,F.path(Ut.position,H))),Ut.action=oy(Et,H)}},ot=(Z,Q)=>{let{room:ht,members:St}=Z,Et=new Map;for(let Ft of St.values())Ft.person.seated&&Ft.key===Ss(za(Ft.desk))&&Et.set(Ft.desk,Ft);ht.screens.forEach((Ft,pe)=>{let ke=Et.get(pe),Nt=ke?.person.action,je=Nt==="type"||Nt==="think"||Nt==="browse",ce=Nt==="browse";Ft.emissive.set(ce?e.dark?"#8ab4ea":"#9cc3f2":je?e.dark?"#3d7bd9":"#4b8fe6":"#203048"),Ft.emissiveIntensity=je?(ce?1:.9)+(z?0:Math.sin(Q*(ce?3:7)+pe)*(ce?.14:.08)):ke?.45:.25});let It=[...St.values()].filter(Ft=>!Ft.actor.lead&&(Ft.actor.state==="working"||Ft.actor.state==="arriving")),Ut=It.map(Ft=>Ft.actor.look.shirt).join();if(Ut!==Z.notesSignature){Z.notesSignature=Ut;for(let Ft of[...ht.notes.children])ht.notes.remove(Ft),Ft.material.dispose();It.forEach((Ft,pe)=>{let ke=new Xt(Q_,new Ae({color:Ft.actor.look.shirt,roughness:.9}));ke.position.set(0,.22-Math.floor(pe/2)*.28,-.45+pe%2*.32),ke.rotation.x=(pe%2?-1:1)*.06,ht.notes.add(ke)})}let y=St.get("lead"),H=[...St.values()].every(Ft=>Ft.actor.lead)&&y!==void 0&&(y.actor.state==="working"||y.actor.state==="answering"||y.actor.state==="waiting"||y.errand!==null)?e.dark?6:2.5:0;ht.deskLamp.intensity+=(H-ht.deskLamp.intensity)*(z?1:.08),ht.printout.visible=[...St.values()].some(Ft=>Ft.errand?.phase==="fetch");let $=[...St.values()].some(Ft=>Math.hypot(Ft.person.position.x-lf.x,Ft.person.position.z-lf.z)<1),mt=ht.sandbox.door,wt=(le.door.x0+le.door.x1)/2-($?(le.door.x1-le.door.x0)*.9:0);mt.position.x+=(wt-mt.position.x)*(z?1:.12);let Ot=[...St.values()].some(Ft=>Ft.actor.spot==="sandbox"&&Ft.person.action==="operate"&&!Ft.person.walking),Vt=[...St.values()].some(Ft=>Ft.actor.spot==="door"&&Ft.actor.state==="waiting"),Jt=z?1:.75+Math.sin(Q*3)*.25;ht.sandbox.strip.color.set(Ot?"#38d39f":Vt?"#f2b33d":e.dark?"#3a4558":"#c4ccd6"),(Ot||Vt)&&ht.sandbox.strip.color.multiplyScalar(Jt*1.4);let se=[...St.values()].some(Ft=>!Ft.gone&&Math.hypot(Ft.person.position.x-zh.x,Ft.person.position.z-zh.z)<1.3);ht.entrance.rotation.y+=((se?j_:0)-ht.entrance.rotation.y)*(z?1:.14);let Bt=[...St.values()].some(Ft=>Ft.actor.state==="working"&&Ft.actor.spot==="table");ht.ring.visible=Bt,Bt&&!z&&(ht.ring.rotation.z=Q*.8,ht.ring.position.y=.95+Math.sin(Q*2)*.03);let ve=[...St.values()].some(Ft=>Ft.person.action==="operate"&&!Ft.person.walking);ht.leds.forEach((Ft,pe)=>{Ft.color.setScalar(ve&&!z?Math.sin(Q*9+pe*Math.PI)>0?1.6:.25:.7)});let Ie=new Date;ht.clock.minute.rotation.z=-((Ie.getMinutes()+Ie.getSeconds()/60)/60)*Math.PI*2,ht.clock.hour.rotation.z=-((Ie.getHours()%12+Ie.getMinutes()/60)/12)*Math.PI*2},yt=Z=>{let Q=tt===null&&E.done(Z);for(let k of V)k.group.position.y=k.y.value(Z),Q&&(Q=k.y.done(Z));M.position.y=E.value(Z);let ht=it(),St=q()&&(ht===void 0||!Q);M.visible=St,w.visible=St,B.position.y=St?Lh-.01:(ht?.group.position.y??0)-.26;for(let k of V){let H=!q()||k===ht;k.group.visible=St||H,k.posts.visible=St,k.room.lamps.forEach(($,mt)=>{$.visible=H&&Q||St&&mt===0}),k.room.deskLamp.visible=H&&Q}let Et=St?Yt():At.height,It=St?Et/2-.5:(ht?.index??0)*Pi+1,Ut=St?Math.max(9,(15+.66*Et)/2+1):9,y=`${It.toFixed(2)}|${Ut.toFixed(2)}`;if(y!==et){et=y,p.target.position.set(0,It,0),p.position.copy(Nh).multiplyScalar(1+Ut/Nh.length()).add(p.target.position);let k=p.shadow.camera;k.left=-Ut,k.right=Ut,k.top=Ut,k.bottom=-Ut,k.far=2*(Nh.length()+Ut)+10,k.updateProjectionMatrix()}let D=`${ht===void 0&&q()?"building":"floor"}|${Q}`;return D!==Dt&&(Dt=D,t.dataset.view=ht===void 0&&q()?"building":"floor",t.dataset.moving=Q?"false":"true"),Q},bt=new O,at=(Z,Q,ht)=>(bt.set(Z,Q,ht).project(c),{x:(bt.x*.5+.5)*i.clientWidth,y:(-bt.y*.5+.5)*i.clientHeight,z:bt.z,visible:bt.z<1&&Math.abs(bt.x)<1.2&&Math.abs(bt.y)<1.2}),lt=Z=>{let Q=ne(),ht=Me(),St=z?1:1-Math.exp(-Z*1.4);return Q.target.distanceTo(ht.target)+Math.abs(Q.radius-ht.radius)*.2+Math.abs(Q.polar-ht.polar)+Math.abs(Q.azimuth-ht.azimuth)<.01?!1:(Kt({target:Q.target.lerp(ht.target,St),radius:en.lerp(Q.radius,ht.radius,St),polar:en.lerp(Q.polar,ht.polar,St),azimuth:en.lerp(Q.azimuth,ht.azimuth,St)}),!0)},Tt=()=>{let Z=it(),Q=gt()&&tt===null;for(let ht of V){let St=ht.group.position.y,Et=(!q()||ht===Z)&&tt===null,It=[...ht.members.values()].map(k=>({member:k,point:at(k.person.position.x,St+k.person.top+.12,k.person.position.z)})).sort((k,H)=>k.point.z-H.point.z),Ut=[];for(let{member:k,point:H}of It){let $=Et&&H.visible&&!k.gone,mt=!1;if($){let wt=k.tagSize;wt||(k.tag.dataset.compact="false",wt=[k.tag.offsetWidth,k.tag.offsetHeight],wt[0]>0&&(k.tagSize=wt));let[Ot,Vt]=wt,Jt=[H.x-Ot/2,H.y-Vt,H.x+Ot/2,H.y];mt=Ut.some(([se,Bt,ve,Ie])=>Jt[0]<ve+2&&Jt[2]>se-2&&Jt[1]<Ie+2&&Jt[3]>Bt-2),mt||Ut.push(Jt)}k.tag.dataset.compact!==String(mt)&&(k.tag.dataset.compact=String(mt)),k.tag.style.transform=`translate(${H.x.toFixed(1)}px, ${H.y.toFixed(1)}px) translate(-50%, -100%)`,k.bubble.style.transform=`translate(${H.x.toFixed(1)}px, ${(H.y-30).toFixed(1)}px) translate(-50%, -100%)`,k.tag.style.visibility=$?"visible":"hidden",k.bubble.style.visibility=$?"visible":"hidden";let Ct=String(Math.round((1-H.z)*1e4));k.tag.style.zIndex=Ct,k.bubble.style.zIndex=Ct}let y=at(At.x1+.4,St+At.height*.5,At.z0+.6),D=Math.max(8,Math.min(y.x+12,i.clientWidth-ht.signWidth-8));ht.sign.style.transform=`translate(${D.toFixed(1)}px, ${y.y.toFixed(1)}px) translate(0, -50%)`,ht.sign.style.visibility=Q&&y.visible?"visible":"hidden",ht.sign.dataset.hover=xt===ht.id?"true":"false"}},J=()=>{o.setPixelRatio(a());let Z=Math.max(1,i.clientWidth),Q=Math.max(1,i.clientHeight);o.setSize(Z,Q,!1),c.aspect=Z/Q,c.updateProjectionMatrix(),!Pt&&i.clientWidth>0&&(Pt=!0,xe(!1))},nt=new ResizeObserver(()=>{J(),Pn()});nt.observe(i),J();let rt=new Fs,pt=new qt,ct=null,vt=Z=>{for(let Q=Z;Q;Q=Q.parent)if(typeof Q.userData.floorId=="string")return Q.userData.floorId;return null},U=Z=>{if(tt)return null;let Q=o.domElement.getBoundingClientRect();if(pt.set((Z.clientX-Q.left)/Q.width*2-1,-((Z.clientY-Q.top)/Q.height)*2+1),rt.setFromCamera(pt,c),gt()){let It=rt.intersectObjects(V.map(y=>y.group),!0)[0],Ut=It?vt(It.object):null;return Ut?{floor:Ut,person:null}:null}let ht=it()??V[0];if(!ht)return null;let St=rt.intersectObjects([...ht.members.values()].filter(It=>!It.gone).map(It=>It.person.root),!0)[0],Et=St?St.object.userData.personId??null:null;return Et?{floor:ht.id,person:Et}:null},ft=0,st=()=>{ft=performance.now()+1500,Pn()},_t=Z=>{ct={x:Z.clientX,y:Z.clientY},st()},Mt=Z=>{if(ct&&Math.hypot(Z.clientX-ct.x,Z.clientY-ct.y)<5){let Q=Uh(t,Z.clientX,Z.clientY),ht=Q?null:U(Z);Q?Q.click():ht?.person?n.pick(ht.floor,ht.person):ht&&n.pickFloor(ht.floor)}ct=null},ut=Z=>{if(Z.buttons){st();return}let Q=U(Z);xt=Q&&!Q.person?Q.floor:null,o.domElement.style.cursor=Q?"pointer":"grab"},Gt=()=>{xt=null};o.domElement.addEventListener("pointerdown",_t),o.domElement.addEventListener("pointerup",Mt),o.domElement.addEventListener("pointermove",ut),o.domElement.addEventListener("pointerleave",Gt),o.domElement.addEventListener("wheel",st,{passive:!0});let kt=Z=>Z.preventDefault();o.domElement.addEventListener("webglcontextlost",kt);let fe=0,ye=performance.now(),xn=0,_n=0,qr=0,Ii=!0,Ys=performance.now(),Es=!0,$i=!0,Li=0,Ki=0,Di=()=>V.some(Z=>[...Z.members.values()].some(Q=>Q.actor.state==="working"||Q.actor.state==="answering"||Q.actor.state==="arriving"||Q.actor.state==="waiting")),Zs=()=>{cancelAnimationFrame(fe),window.clearTimeout(Li),fe=0,Li=0};function Pn(){Ys=performance.now(),Es=!0,i.dataset.sleeping="false",fe===0&&$i&&!G&&!document.hidden&&(window.clearTimeout(Li),Li=0,ye=performance.now(),fe=requestAnimationFrame(Ts))}let Yr=Z=>{if(Z<=50){fe=requestAnimationFrame(Ts);return}Li=window.setTimeout(()=>{Li=0,fe===0&&$i&&!G&&!document.hidden&&(fe=requestAnimationFrame(Ts))},Z-16)},ws=Z=>tt?af:r==="backdrop"?Ii||Z<Ki?ry:ay:Ii||Z<ft||Z<Ki?af:ny,Ts=Z=>{if(fe=0,G||!$i||document.hidden)return;let Q=ws(Z);if(Z-xn<Q-2){Yr(Q-(Z-xn));return}xn=Z;let ht=performance.now(),St=Math.min(.05,(Z-ye)/1e3);ye=Z;let Et=Z/1e3,It=!1;if(!X)for(let y of V){j(y,Et);for(let D of y.members.values())D.person.update(St,Et,z),It||(It=D.person.walking);ot(y,Et)}Ii=yt(Et)===!1||It||tt!==null,tt?ze(Et):r==="backdrop"?Ii=lt(St)||Ii:h.update(),(Ii||Es||Z<Ki)&&(o.shadowMap.needsUpdate=!0,Es=!1),o.render(l,c),r==="room"&&Tt(),qr+=performance.now()-ht,_n+=1,_n>=60&&(i.dataset.drawCalls=String(o.info.render.calls),i.dataset.triangles=String(o.info.render.triangles),i.dataset.frameMs=(qr/_n).toFixed(2),_n=0,qr=0);let Ut=performance.now();(Ii||Ut<ft||Ut<Ki||Di()&&!X)&&(Ys=Ut),Ut-Ys<iy?Yr(ws(Ut)):i.dataset.sleeping="true"},As=()=>{document.hidden||Pn()};return document.addEventListener("visibilitychange",As),fe=requestAnimationFrame(Ts),{update(Z){G||(K(Z),Pn())},focus(Z){G||!q()||(Y=Z!==null&&P.has(Z)?Z:null,Ne(performance.now()/1e3),Pn())},setPaused(Z){X=Z,Pn()},setMode(Z){G||Z===r||(r=Z,i.dataset.mode=Z,h.enabled=!1,J(),xe(!0),Pn())},setActive(Z){G||Z===$i||($i=Z,i.dataset.active=String(Z),$i?Pn():Zs())},resetView(){xe(!0),Pn()},exercise(Z){G||(Ki=performance.now()+Z,Pn())},dispose(){G=!0,Zs(),document.removeEventListener("visibilitychange",As),nt.disconnect(),o.domElement.removeEventListener("pointerdown",_t),o.domElement.removeEventListener("pointerup",Mt),o.domElement.removeEventListener("pointermove",ut),o.domElement.removeEventListener("pointerleave",Gt),o.domElement.removeEventListener("wheel",st),o.domElement.removeEventListener("webglcontextlost",kt),h.dispose();for(let Z of P.values())C(Z);P.clear(),V=[],M.removeFromParent(),w.removeFromParent();for(let Z of[M,w])Z.traverse(Q=>{Q instanceof Xt&&Q.geometry.dispose()});for(let Z of R)Z.geometry.dispose();B.removeFromParent(),B.geometry.dispose(),B.material.dispose(),N.dispose(),_.dispose(),Fl(f),o.dispose(),o.forceContextLoss(),o.domElement.remove()}}}var ly=1e3/30,cy=1e3/12,hy=4e3,uy=1.2,dy=.7,Fh=new O(-5,11,8),Oh="__hover";function fy(i){return i<.5?4*i*i*i:1-(-2*i+2)**3/2}function uf(i,t,e,n,s){let r=new Dr({antialias:!0,alpha:!0,powerPreference:"low-power"});r.setPixelRatio(Math.min(window.devicePixelRatio||1,1.25)),r.shadowMap.enabled=!0,r.shadowMap.type=Gi,r.shadowMap.autoUpdate=!1,r.outputColorSpace=He,r.toneMapping=Bs,r.toneMappingExposure=e.dark?1.05:1,r.domElement.classList.add("studio-canvas"),r.domElement.setAttribute("aria-hidden","true"),i.prepend(r.domElement);let a=new Ds,o=new Ye(30,1,.5,260),l=new Vr(o,r.domElement);l.enableDamping=!0,l.dampingFactor=.08,l.enablePan=!1,l.rotateSpeed=.6,l.zoomSpeed=.8,a.add(new Us(e.dark?"#9fb0e0":"#fff6ea",e.dark?"#3a3040":"#b8a48c",e.dark?1.35:1.5));let c=new Vi(e.dark?"#b9c8ff":"#fff1dc",e.dark?1.5:2.2);c.castShadow=!0,c.shadow.mapSize.set(1024,1024),c.shadow.camera.near=1,c.shadow.bias=-6e-4,c.shadow.radius=3,a.add(c,c.target);let h=new Vi(e.dark?"#5b4b8a":"#cfe3ff",e.dark?.35:.6);h.position.set(9,5,-3),a.add(h);let p=Ul(),d=new ae;a.add(d);let f=e.reducedMotion,_=[],b=n({root:d,finishes:p,options:e,still:f,pickable(J,nt){J.traverse(rt=>{typeof nt=="function"?rt.userData.pickInstance=nt:rt.userData.pick=nt}),_.push(J)}}),{min:m,max:u}=b.frame,S=new O((m.x+u.x)/2,(m.y+u.y)/2,(m.z+u.z)/2),R=Math.max(u.x-m.x,u.z-m.z)/2+2;c.target.position.copy(S),c.position.copy(Fh).multiplyScalar(1+R/Fh.length()).add(S),Object.assign(c.shadow.camera,{left:-R,right:R,top:R,bottom:-R,far:2*(Fh.length()+R)+10}),c.shadow.camera.updateProjectionMatrix();let v=(b.lamps??[]).map(J=>{let nt=new yi(J.colour??"#ffcf8a",e.dark?9:2.5,9,1.4);return nt.position.set(J.x,J.y,J.z),a.add(nt),nt}),M=(J,nt,rt)=>{let pt=new O().setFromSpherical(new Tn(1,nt,rt)),ct=new O(0,1,0).cross(pt).normalize(),vt=pt.clone().cross(ct),U=Math.tan(en.degToRad(o.fov)/2),ft=U*o.aspect,st=new O,_t=0;for(let Mt=0;Mt<8;Mt+=1){st.set(Mt&1?u.x:m.x,Mt&2?u.y:m.y,Mt&4?u.z:m.z).sub(J);let ut=st.dot(pt);_t=Math.max(_t,ut+Math.abs(st.dot(ct))/ft,ut+Math.abs(st.dot(vt))/U)}return _t},E=()=>{let J=o.aspect<1,nt=J?Math.max(.45,b.frame.polar-.25):b.frame.polar;return{target:S.clone(),radius:M(S,nt,b.frame.azimuth)*(J?.9:1.03),polar:nt,azimuth:b.frame.azimuth}},A=()=>{let J=new Tn().setFromVector3(o.position.clone().sub(l.target));return{target:l.target.clone(),radius:J.radius,polar:J.phi,azimuth:J.theta}},g=J=>{l.target.copy(J.target),o.position.setFromSpherical(new Tn(J.radius,J.polar,J.azimuth)).add(J.target),o.lookAt(J.target)},w=()=>{let J=E();l.minDistance=J.radius*.4,l.maxDistance=J.radius*1.5,l.minPolarAngle=.3,l.maxPolarAngle=1.4,l.minAzimuthAngle=J.azimuth-1.1,l.maxAzimuthAngle=J.azimuth+1},T=null,I=(J,nt,rt)=>{if(f||nt<=0){g(J),l.update(),rt?.();return}T={from:A(),to:J,start:performance.now()/1e3,seconds:nt,...rt?{done:rt}:{}},l.enabled=!1},N=J=>{if(!T)return;let nt=fy(Math.min(1,(J-T.start)/T.seconds)),{from:rt,to:pt}=T;if(g({target:rt.target.clone().lerp(pt.target,nt),radius:en.lerp(rt.radius,pt.radius,nt),polar:en.lerp(rt.polar,pt.polar,nt),azimuth:en.lerp(rt.azimuth,pt.azimuth,nt)}),J-T.start>=T.seconds){let ct=T.done;T=null,l.enabled=!0,l.update(),ct?.()}},B=new Map,F=!0,P=performance.now(),V=4e3,z=J=>{let{actor:nt,tag:rt,bubble:pt}=J;rt.dataset.state=nt.state,rt.querySelector(".studio-tag-name").textContent=nt.name,rt.querySelector(".studio-tag-state").textContent=nt.stateLabel,rt.setAttribute("aria-label",`${nt.name}: ${nt.stateLabel}`),pt.textContent=nt.bubble??"",pt.hidden=!nt.bubble,pt.dataset.state=nt.state},X=J=>{let nt=F||performance.now()-P<V,rt=nt||!b.floor?J.place:b.floor.door,pt=new Gr(J.id,J.look,rt,e.accent,p);nt&&(pt.heading=Math.atan2(J.place.face.x-J.place.x,J.place.face.z-J.place.z)),d.add(pt.root);let ct=document.createElement("button");ct.type="button",ct.className="studio-tag",ct.tabIndex=-1;for(let ft of["studio-tag-dot","studio-tag-name","studio-tag-state"]){let st=document.createElement("span");st.className=ft,ct.append(st)}ct.addEventListener("click",()=>{U.actor.pick&&s.pick(U.actor.pick)});let vt=document.createElement("div");vt.className="studio-bubble",t.append(vt,ct);let U={person:pt,actor:J,tag:ct,bubble:vt,key:""};return z(U),U},G=J=>{J.person.dispose(),J.tag.remove(),J.bubble.remove()},Y=new Map,tt={},et=null,dt=J=>{for(let[nt,rt]of Y)J[nt]||(rt.element.remove(),Y.delete(nt));for(let[nt,rt]of Object.entries(J)){let pt=Y.get(nt);if(!pt){let U=document.createElement("button");U.type="button",U.className="studio-floor-sign place-sign",U.tabIndex=-1;for(let ft of["studio-floor-title","studio-floor-summary"]){let st=document.createElement("span");st.className=ft,U.append(st)}U.addEventListener("click",()=>{let ft=Y.get(nt)?.label.pick;ft&&s.pick(ft)}),t.append(U),pt={element:U,label:rt,width:0,height:0},Y.set(nt,pt)}pt.label=rt;let{element:ct}=pt;ct.dataset.busy=rt.tone==="busy"?"true":"false",ct.dataset.tone=rt.tone??"",ct.dataset.pick=rt.pick?"true":"false",ct.querySelector(".studio-floor-title").textContent=rt.title;let vt=ct.querySelector(".studio-floor-summary");vt.textContent=rt.detail??"",vt.hidden=!rt.detail,ct.setAttribute("aria-label",rt.detail?`${rt.title}: ${rt.detail}`:rt.title),pt.width=ct.offsetWidth,pt.height=ct.offsetHeight}},Dt=!1,Pt=!1,xt=J=>{let nt=performance.now()/1e3,{people:rt,labels:pt}=b.update(J,nt),ct=new Set(rt.map(U=>U.id));for(let[U,ft]of B)ct.has(U)||(G(ft),B.delete(U));for(let U of rt){let ft=B.get(U.id);ft?(ft.actor.state!==U.state&&U.state==="done"&&ft.person.cheer(nt),ft.actor=U,z(ft)):B.set(U.id,X(U))}F=!1,tt=pt;let vt=et?b.hover?.(et)??null:null;dt(vt?{...pt,[Oh]:vt}:pt)},q=new O,it=(J,nt,rt)=>(q.set(J,nt,rt).project(o),{x:(q.x*.5+.5)*i.clientWidth,y:(-q.y*.5+.5)*i.clientHeight,z:q.z,visible:q.z<1&&Math.abs(q.x)<1.15&&Math.abs(q.y)<1.15}),gt=()=>{let J=T===null;for(let ct of B.values()){let vt=it(ct.person.position.x,ct.person.top+.12,ct.person.position.z),U=J&&vt.visible;ct.tag.style.transform=`translate(${vt.x.toFixed(1)}px, ${vt.y.toFixed(1)}px) translate(-50%, -100%)`,ct.bubble.style.transform=`translate(${vt.x.toFixed(1)}px, ${(vt.y-30).toFixed(1)}px) translate(-50%, -100%)`,ct.tag.style.visibility=U?"visible":"hidden",ct.bubble.style.visibility=U?"visible":"hidden";let ft=String(Math.round((1-vt.z)*1e4));ct.tag.style.zIndex=ft,ct.bubble.style.zIndex=ft}let nt=(ct,vt)=>ct===Oh?0:vt.label.tone==="alert"?1:vt.label.tone==="busy"?2:3,rt=[...Y.entries()].map(([ct,vt])=>({id:ct,sign:vt,point:it(vt.label.at.x,vt.label.at.y,vt.label.at.z)})).sort((ct,vt)=>nt(ct.id,ct.sign)-nt(vt.id,vt.sign)||ct.point.z-vt.point.z),pt=[];for(let{sign:ct,point:vt}of rt){let U=Math.max(8,Math.min(vt.x-ct.width/2,i.clientWidth-ct.width-8)),ft=[U,vt.y-ct.height,U+ct.width,vt.y],st=!pt.some(([Mt,ut,Gt,kt])=>ft[0]<Gt+3&&ft[2]>Mt-3&&ft[1]<kt+3&&ft[3]>ut-3),_t=J&&vt.visible&&st;_t&&pt.push(ft),ct.element.style.transform=`translate(${U.toFixed(1)}px, ${vt.y.toFixed(1)}px) translate(0, -100%)`,ct.element.style.visibility=_t?"visible":"hidden",ct.element.style.zIndex=String(Math.round((1-vt.z)*1e4))}t.dataset.moving=T?"true":"false"},zt=!1,Rt=()=>{let J=Math.max(1,i.clientWidth),nt=Math.max(1,i.clientHeight);if(r.setSize(J,nt,!1),o.aspect=J/nt,o.updateProjectionMatrix(),!zt&&i.clientWidth>0){zt=!0;let rt=E();g({...rt,radius:rt.radius*1.45,polar:Math.max(.35,rt.polar-.18),azimuth:rt.azimuth+.3}),w(),I(rt,uy)}},Yt=new ResizeObserver(()=>{Rt(),at()});Yt.observe(i),Rt();let Me=new Fs,Qt=new qt,ne=null,Kt=0,te=J=>{if(T)return null;let nt=r.domElement.getBoundingClientRect();Qt.set((J.clientX-nt.left)/nt.width*2-1,-((J.clientY-nt.top)/nt.height)*2+1),Me.setFromCamera(Qt,o);let rt=[...B.values()].map(pt=>pt.person.root);for(let pt of Me.intersectObjects([...rt,..._],!0)){let ct=pt.object.userData.personId,vt=pt.object.userData.pickInstance,U=ct?B.get(ct)?.actor.pick:vt&&pt.instanceId!==void 0?vt(pt.instanceId):pt.object.userData.pick;if(U)return U}return null},xe=J=>{ne={x:J.clientX,y:J.clientY},Kt=performance.now()+1500,at()},ze=J=>{if(ne&&Math.hypot(J.clientX-ne.x,J.clientY-ne.y)<5){let nt=Uh(t,J.clientX,J.clientY),rt=nt?null:te(J);nt?nt.click():rt&&s.pick(rt)}ne=null},Ne=J=>{if(J.buttons){Kt=performance.now()+1500,at();return}let nt=te(J);if(r.domElement.style.cursor=nt?"pointer":"grab",nt!==et){et=nt;let rt=nt?b.hover?.(nt)??null:null;dt(rt?{...tt,[Oh]:rt}:tt)}},ge=()=>{et!==null&&(et=null,dt(tt))},Ee=()=>{Kt=performance.now()+1500,at()},W=J=>J.preventDefault();r.domElement.addEventListener("pointerdown",xe),r.domElement.addEventListener("pointerup",ze),r.domElement.addEventListener("pointermove",Ne),r.domElement.addEventListener("pointerleave",ge),r.domElement.addEventListener("wheel",Ee,{passive:!0}),r.domElement.addEventListener("webglcontextlost",W);let Pe=0,_e=0,C=performance.now(),x=!0,K=0,j=0,ot=performance.now(),yt=!0,bt=()=>[...B.values()].some(J=>J.actor.state==="working"||J.actor.state==="waiting");function at(){ot=performance.now(),yt=!0,i.dataset.sleeping="false",Pe===0&&!Pt&&!document.hidden&&(C=performance.now(),Pe=requestAnimationFrame(lt))}let lt=J=>{if(Pe=0,Pt||document.hidden)return;let nt=x||J<Kt||T?ly:cy;if(J-_e<nt-2){Pe=requestAnimationFrame(lt);return}_e=J;let rt=performance.now(),pt=Math.min(.05,(J-C)/1e3);C=J;let ct=J/1e3,vt=!1;if(!Dt){for(let ft of B.values()){let{actor:st,person:_t}=ft,Mt=`${st.place.x.toFixed(2)},${st.place.z.toFixed(2)}`;Mt!==ft.key&&(ft.key=Mt,_t.goTo(st.place,b.floor?b.floor.grid.path(_t.position,st.place):[st.place])),_t.action=st.action,_t.update(pt,ct,f),vt||(vt=_t.walking)}vt=b.tick(ct,pt)||vt}x=vt||T!==null,T?N(ct):l.update(),(x||yt)&&(r.shadowMap.needsUpdate=!0,yt=!1),r.render(a,o),gt(),j+=performance.now()-rt,K+=1,K>=60&&(i.dataset.drawCalls=String(r.info.render.calls),i.dataset.triangles=String(r.info.render.triangles),i.dataset.frameMs=(j/K).toFixed(2),K=0,j=0);let U=performance.now();(x||U<Kt||bt()&&!Dt)&&(ot=U),U-ot<hy?Pe=requestAnimationFrame(lt):i.dataset.sleeping="true"},Tt=()=>{document.hidden||at()};return document.addEventListener("visibilitychange",Tt),Pe=requestAnimationFrame(lt),{update(J){Pt||(xt(J),at())},setPaused(J){Dt=J,at()},resetView(){I(E(),.9),at()},approach(J){let nt=b.target?.(J);if(!nt||Pt)return Promise.resolve();let rt=A();return at(),new Promise(pt=>I({target:new O(nt.x,nt.y,nt.z),radius:rt.radius*.35,polar:Math.min(rt.polar+.15,1.3),azimuth:rt.azimuth},dy,pt))},dispose(){Pt=!0,cancelAnimationFrame(Pe),document.removeEventListener("visibilitychange",Tt),Yt.disconnect(),r.domElement.removeEventListener("pointerdown",xe),r.domElement.removeEventListener("pointerup",ze),r.domElement.removeEventListener("pointermove",Ne),r.domElement.removeEventListener("pointerleave",ge),r.domElement.removeEventListener("wheel",Ee),r.domElement.removeEventListener("webglcontextlost",W),l.dispose();for(let J of B.values())G(J);B.clear();for(let J of Y.values())J.element.remove();Y.clear(),b.dispose();for(let J of v)J.dispose();d.removeFromParent(),Fl(p),r.dispose(),r.forceContextLoss(),r.domElement.remove()}}}var py={campus:zd,library:Jd,site:jd,duty:Yd,desk:qd};window.AgentStudio={createStudioScene:hf,createPlaceScene:uf,places:py};})();
