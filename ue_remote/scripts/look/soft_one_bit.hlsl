float2 uv = GetDefaultSceneTextureUV(Parameters, 14);
float2 texel = View.BufferSizeAndInvSize.zw;

float3 color = SceneTextureLookup(uv, 14, false).rgb;
float luminance = saturate((dot(color, float3(0.299, 0.587, 0.114)) - 0.5) * Contrast + 0.5);

float2 cell = floor(uv * View.BufferSizeAndInvSize.xy / max(PixelScale, 1.0));
float threshold = Bayer.SampleLevel(BayerSampler, (fmod(cell, 8.0) + 0.5) / 8.0, 0).r;

float steps = max(Tones - 1.0, 1.0);
float scaled = luminance * steps;
float dithered = (floor(scaled) + step(threshold, frac(scaled))) / steps;
float banded = round(scaled) / steps;
float tone = lerp(banded, dithered, DitherAmount);

float depth = SceneTextureLookup(uv, 1, false).r;
float depthEdge = abs(SceneTextureLookup(uv + float2(texel.x, 0), 1, false).r - depth)
                + abs(SceneTextureLookup(uv - float2(texel.x, 0), 1, false).r - depth)
                + abs(SceneTextureLookup(uv + float2(0, texel.y), 1, false).r - depth)
                + abs(SceneTextureLookup(uv - float2(0, texel.y), 1, false).r - depth);
depthEdge /= max(depth, 1.0);

float3 normal = SceneTextureLookup(uv, 8, false).rgb;
float normalEdge = distance(SceneTextureLookup(uv + float2(texel.x, 0), 8, false).rgb, normal)
                 + distance(SceneTextureLookup(uv + float2(0, texel.y), 8, false).rgb, normal);

float edge = saturate(step(DepthThreshold, depthEdge) + step(NormalThreshold, normalEdge));
float3 shade = lerp(Ink, Paper, tone);
float3 outline = tone > 0.5 ? Ink : Paper;
return lerp(shade, outline, edge * OutlineStrength);
