float2 uv = GetDefaultSceneTextureUV(Parameters, 14);
float2 texel = View.BufferSizeAndInvSize.zw * Softness;

float3 color = SceneTextureLookup(uv, 14, false).rgb * 0.4
             + SceneTextureLookup(uv + float2(texel.x, 0), 14, false).rgb * 0.15
             + SceneTextureLookup(uv - float2(texel.x, 0), 14, false).rgb * 0.15
             + SceneTextureLookup(uv + float2(0, texel.y), 14, false).rgb * 0.15
             + SceneTextureLookup(uv - float2(0, texel.y), 14, false).rgb * 0.15;

float luminance = dot(color, float3(0.299, 0.587, 0.114));
return lerp(luminance.xxx, color, Saturation) * Tint;
