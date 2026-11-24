// IrisData.m - Centralized mock data models and store implementation
#import "IrisData.h"
#import "IrisTheme.h"

@implementation IrisComment
@end

@implementation IrisPost
- (instancetype)init {
    self = [super init];
    if (self) {
        _comments = [NSMutableArray array];
        _aspectRatio = 1.0;
    }
    return self;
}
@end

@implementation IrisStory
@end

@implementation IrisProfile
@end

@implementation IrisNotification
@end

@implementation IrisData

+ (instancetype)sharedData {
    static IrisData *sSharedData = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        sSharedData = [[IrisData alloc] init];
    });
    return sSharedData;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        [self bootstrapMockData];
    }
    return self;
}

- (void)bootstrapMockData {
    _posts = [NSMutableArray array];
    _stories = [NSMutableArray array];
    _profiles = [NSMutableDictionary dictionary];
    _notifications = [NSMutableArray array];
    
    // 1. Current user profile
    _currentUserProfile = [[IrisProfile alloc] init];
    _currentUserProfile.username = @"alex";
    _currentUserProfile.displayName = @"Alex Mercer";
    _currentUserProfile.avatar = @"avatar_alex";
    _currentUserProfile.bio = @"Visual designer & urban photographer 📸\nCapturing neon nights & architecture 🏙️";
    _currentUserProfile.website = @"alexmercer.design";
    _currentUserProfile.postsCount = 42;
    _currentUserProfile.followersCount = 14850;
    _currentUserProfile.followingCount = 482;
    _currentUserProfile.isFollowing = NO;
    _currentUserProfile.postImages = @[@"post_arch1", @"post_neon1", @"post_nature1", @"post_street1", @"post_travel1", @"post_coffee1", @"post_mountain1", @"post_portrait1", @"post_minimal1"];
    [_profiles setObject:_currentUserProfile forKey:@"alex"];
    
    // 2. Additional Mock Profiles (At least 5 distinct profiles)
    IrisProfile *maya = [[IrisProfile alloc] init];
    maya.username = @"maya";
    maya.displayName = @"Maya Sharma";
    maya.avatar = @"avatar_maya";
    maya.bio = @"Nomad wanderer & landscape photographer 🌍\nSearching for golden hours across Rajasthan.";
    maya.website = @"mayasharma.photo";
    maya.postsCount = 128;
    maya.followersCount = 38900;
    maya.followingCount = 612;
    maya.isFollowing = YES;
    maya.postImages = @[@"post_jaipur1", @"post_mountain2", @"post_desert1", @"post_travel2", @"post_palace1", @"post_sunset1", @"post_tea1", @"post_portrait2", @"post_market1"];
    [_profiles setObject:maya forKey:@"maya"];
    
    IrisProfile *jordan = [[IrisProfile alloc] init];
    jordan.username = @"jordan";
    jordan.displayName = @"Jordan Vance";
    jordan.avatar = @"avatar_jordan";
    jordan.bio = @"Minimalist architecture & brutalist lines.\nBerlin / Tokyo / Seoul.";
    jordan.website = @"jordanvance.co";
    jordan.postsCount = 85;
    jordan.followersCount = 22400;
    jordan.followingCount = 310;
    jordan.isFollowing = NO;
    jordan.postImages = @[@"post_brutalist1", @"post_arch2", @"post_tokyo1", @"post_stairs1", @"post_museum1", @"post_shadows1", @"post_glass1", @"post_concrete1", @"post_sculpture1"];
    [_profiles setObject:jordan forKey:@"jordan"];
    
    IrisProfile *sara = [[IrisProfile alloc] init];
    sara.username = @"sara";
    sara.displayName = @"Sara Chen";
    sara.avatar = @"avatar_sara";
    sara.bio = @"Culinary explorer & specialty coffee geek ☕\nDocumenting pastries, roasters and flavor profiles.";
    sara.website = @"saracooksandbrews.com";
    sara.postsCount = 94;
    sara.followersCount = 18700;
    sara.followingCount = 520;
    sara.isFollowing = YES;
    sara.postImages = @[@"post_coffee2", @"post_pastry1", @"post_latteart1", @"post_cafe1", @"post_beans1", @"post_bakery1", @"post_tea2", @"post_matcha1", @"post_dessert1"];
    [_profiles setObject:sara forKey:@"sara"];
    
    IrisProfile *dev = [[IrisProfile alloc] init];
    dev.username = @"dev";
    dev.displayName = @"Dev Patel";
    dev.avatar = @"avatar_dev";
    dev.bio = @"Street lifestyle & medium format film 🎞️\nEvery street corner tells a story.";
    dev.website = @"devfilm.studio";
    dev.postsCount = 156;
    dev.followersCount = 45200;
    dev.followingCount = 390;
    dev.isFollowing = NO;
    dev.postImages = @[@"post_street2", @"post_film1", @"post_vintage1", @"post_neon2", @"post_rain1", @"post_subway1", @"post_night1", @"post_cafe2", @"post_car1"];
    [_profiles setObject:dev forKey:@"dev"];
    
    IrisProfile *emily = [[IrisProfile alloc] init];
    emily.username = @"emily";
    emily.displayName = @"Emily Thorne";
    emily.avatar = @"avatar_emily";
    emily.bio = @"Nordic trails, alpine peaks & quiet cabins 🏔️\nChasing mist in the fjords.";
    emily.website = @"emilythorne.travel";
    emily.postsCount = 112;
    emily.followersCount = 29400;
    emily.followingCount = 415;
    emily.isFollowing = YES;
    emily.postImages = @[@"post_nordic1", @"post_cabin1", @"post_fjord1", @"post_lake1", @"post_forest1", @"post_hike1", @"post_glacier1", @"post_campfire1", @"post_stars1"];
    [_profiles setObject:emily forKey:@"emily"];
    
    // 3. Stories (8-12 mock users)
    IrisStory *s0 = [[IrisStory alloc] init];
    s0.storyId = @"story_0";
    s0.username = @"alex";
    s0.avatar = @"avatar_alex";
    s0.imageKey = @"story_alex_img";
    s0.timestamp = @"Just now";
    s0.viewed = NO;
    s0.isYourStory = YES;
    [_stories addObject:s0];
    
    NSArray *storyUsers = @[
        @{@"u": @"maya", @"a": @"avatar_maya", @"k": @"story_maya_img", @"t": @"25m ago", @"v": @NO},
        @{@"u": @"jordan", @"a": @"avatar_jordan", @"k": @"story_jordan_img", @"t": @"1h ago", @"v": @NO},
        @{@"u": @"sara", @"a": @"avatar_sara", @"k": @"story_sara_img", @"t": @"2h ago", @"v": @NO},
        @{@"u": @"dev", @"a": @"avatar_dev", @"k": @"story_dev_img", @"t": @"3h ago", @"v": @YES},
        @{@"u": @"arjun", @"a": @"avatar_arjun", @"k": @"story_arjun_img", @"t": @"4h ago", @"v": @NO},
        @{@"u": @"emily", @"a": @"avatar_emily", @"k": @"story_emily_img", @"t": @"5h ago", @"v": @NO},
        @{@"u": @"noah", @"a": @"avatar_noah", @"k": @"story_noah_img", @"t": @"7h ago", @"v": @YES},
        @{@"u": @"clara", @"a": @"avatar_clara", @"k": @"story_clara_img", @"t": @"8h ago", @"v": @NO},
        @{@"u": @"liam", @"a": @"avatar_liam", @"k": @"story_liam_img", @"t": @"10h ago", @"v": @YES},
        @{@"u": @"zara", @"a": @"avatar_zara", @"k": @"story_zara_img", @"t": @"12h ago", @"v": @NO}
    ];
    
    for (int i = 0; i < (int)storyUsers.count; i++) {
        NSDictionary *dict = storyUsers[i];
        IrisStory *s = [[IrisStory alloc] init];
        s.storyId = [NSString stringWithFormat:@"story_%d", i + 1];
        s.username = dict[@"u"];
        s.avatar = dict[@"a"];
        s.imageKey = dict[@"k"];
        s.timestamp = dict[@"t"];
        s.viewed = [dict[@"v"] boolValue];
        s.isYourStory = NO;
        [_stories addObject:s];
    }
    
    // 4. Feed Posts (At least 10 realistic mock posts)
    NSArray *mockPostConfigs = @[
        @{
            @"id": @"p1", @"user": @"maya", @"name": @"Maya Sharma", @"avatar": @"avatar_maya",
            @"loc": @"Jaipur, India",
            @"cap": @"Somewhere between the mountains and the sky ✨",
            @"tags": @"#travel #photography #weekend #wanderlust",
            @"likes": @12842, @"comments": @142, @"time": @"2 hours ago",
            @"img": @"post_jaipur1", @"ratio": @1.25, @"isLiked": @NO, @"isBookmarked": @NO,
            @"c1_u": @"alex", @"c1_t": @"Beautiful view!",
            @"c2_u": @"dev", @"c2_t": @"The lighting in this is magical 🌅"
        },
        @{
            @"id": @"p2", @"user": @"jordan", @"name": @"Jordan Vance", @"avatar": @"avatar_jordan",
            @"loc": @"Ginza, Tokyo",
            @"cap": @"Minimal geometric harmony. Raw concrete meets amber sunset reflections.",
            @"tags": @"#brutalism #tokyo #architecture #minimal",
            @"likes": @8420, @"comments": @98, @"time": @"3 hours ago",
            @"img": @"post_arch2", @"ratio": @1.0, @"isLiked": @YES, @"isBookmarked": @YES,
            @"c1_u": @"maya", @"c1_t": @"Cleanest lines I have ever seen.",
            @"c2_u": @"sara", @"c2_t": @"Almost looks like a 3D render!"
        },
        @{
            @"id": @"p3", @"user": @"sara", @"name": @"Sara Chen", @"avatar": @"avatar_sara",
            @"loc": @"Fika Lab, Stockholm",
            @"cap": @"Morning dial-in on the washed Ethiopian heirloom. Floral jasmine notes with peach brightness ☕🌸",
            @"tags": @"#specialtycoffee #pourover #ethiopia #fika",
            @"likes": @4315, @"comments": @64, @"time": @"5 hours ago",
            @"img": @"post_coffee2", @"ratio": @1.2, @"isLiked": @NO, @"isBookmarked": @NO,
            @"c1_u": @"alex", @"c1_t": @"Need a cup of that right now!",
            @"c2_u": @"noah", @"c2_t": @"What brew ratio are you using?"
        },
        @{
            @"id": @"p4", @"user": @"dev", @"name": @"Dev Patel", @"avatar": @"avatar_dev",
            @"loc": @"Shinjuku Nightwalk",
            @"cap": @"Neon reflections in the post-midnight rain. 35mm Portra 800.",
            @"tags": @"#filmphotography #35mm #cinematic #nightphotography",
            @"likes": @19280, @"comments": @312, @"time": @"6 hours ago",
            @"img": @"post_neon2", @"ratio": @1.25, @"isLiked": @YES, @"isBookmarked": @NO,
            @"c1_u": @"emily", @"c1_t": @"The tones here are unbeatable.",
            @"c2_u": @"jordan", @"c2_t": @"Blade Runner vibes ✨"
        },
        @{
            @"id": @"p5", @"user": @"emily", @"name": @"Emily Thorne", @"avatar": @"avatar_emily",
            @"loc": @"Lofoten Islands, Norway",
            @"cap": @"Midnight sun grazing the icy peaks. Total silence except for arctic waves.",
            @"tags": @"#norway #lofoten #nordic #polar #nature",
            @"likes": @24600, @"comments": @408, @"time": @"8 hours ago",
            @"img": @"post_nordic1", @"ratio": @1.0, @"isLiked": @NO, @"isBookmarked": @YES,
            @"c1_u": @"alex", @"c1_t": @"Breathtaking scene Emily!",
            @"c2_u": @"maya", @"c2_t": @"Adding Lofoten to my dream list right now."
        },
        @{
            @"id": @"p6", @"user": @"arjun", @"name": @"Arjun Mehta", @"avatar": @"avatar_arjun",
            @"loc": @"Leh-Ladakh, Himalayas",
            @"cap": @"Highest motorable passes in the world. Cold air, hot chai, and unending valleys.",
            @"tags": @"#ladakh #himalayas #roadtrip #wanderer",
            @"likes": @15390, @"comments": @221, @"time": @"11 hours ago",
            @"img": @"post_mountain1", @"ratio": @1.25, @"isLiked": @NO, @"isBookmarked": @NO,
            @"c1_u": @"dev", @"c1_t": @"Incredible altitude!",
            @"c2_u": @"sara", @"c2_t": @"Stay warm up there!"
        },
        @{
            @"id": @"p7", @"user": @"noah", @"name": @"Noah Williams", @"avatar": @"avatar_noah",
            @"loc": @"Dolomites, Italy",
            @"cap": @"Alpenglow igniting Tre Cime di Lavaredo at dusk.",
            @"tags": @"#dolomites #alps #italy #mountains #sunset",
            @"likes": @18100, @"comments": @195, @"time": @"14 hours ago",
            @"img": @"post_mountain2", @"ratio": @1.0, @"isLiked": @YES, @"isBookmarked": @YES,
            @"c1_u": @"emily", @"c1_t": @"That pink gradient on the rocks is pure magic.",
            @"c2_u": @"maya", @"c2_t": @"Stunning capture Noah."
        },
        @{
            @"id": @"p8", @"user": @"clara", @"name": @"Clara Dupont", @"avatar": @"avatar_clara",
            @"loc": @"Montmartre, Paris",
            @"cap": @"Morning light spilling through the atelier windows. Fresh croissants on table.",
            @"tags": @"#paris #montmartre #lifestyle #aesthetic",
            @"likes": @9230, @"comments": @87, @"time": @"18 hours ago",
            @"img": @"post_cafe1", @"ratio": @1.25, @"isLiked": @NO, @"isBookmarked": @NO,
            @"c1_u": @"sara", @"c1_t": @"Save a croissant for me!",
            @"c2_u": @"alex", @"c2_t": @"Classic Parisian morning."
        },
        @{
            @"id": @"p9", @"user": @"liam", @"name": @"Liam Gallagher", @"avatar": @"avatar_liam",
            @"loc": @"Isle of Skye, Scotland",
            @"cap": @"Moody mist wrapping around the Old Man of Storr. Unpredictable Scottish weather.",
            @"tags": @"#scotland #highlands #skye #fog #moodygrams",
            @"likes": @11450, @"comments": @130, @"time": @"1 day ago",
            @"img": @"post_scotland1", @"ratio": @1.0, @"isLiked": @NO, @"isBookmarked": @NO,
            @"c1_u": @"noah", @"c1_t": @"Nothing beats Scottish atmosphere.",
            @"c2_u": @"dev", @"c2_t": @"Dramatic contrast!"
        },
        @{
            @"id": @"p10", @"user": @"zara", @"name": @"Zara Al-Mansoor", @"avatar": @"avatar_zara",
            @"loc": @"Muscat, Oman",
            @"cap": @"Intricate geometric Islamic arches glowing under the midday sun.",
            @"tags": @"#oman #architecture #symmetry #heritage",
            @"likes": @13740, @"comments": @168, @"time": @"1 day ago",
            @"img": @"post_arch1", @"ratio": @1.25, @"isLiked": @YES, @"isBookmarked": @NO,
            @"c1_u": @"jordan", @"c1_t": @"The precision of those arches is unreal.",
            @"c2_u": @"maya", @"c2_t": @"Truly majestic architecture."
        }
    ];
    
    for (NSDictionary *cfg in mockPostConfigs) {
        IrisPost *p = [[IrisPost alloc] init];
        p.postId = cfg[@"id"];
        p.username = cfg[@"user"];
        p.displayName = cfg[@"name"];
        p.avatar = cfg[@"avatar"];
        p.location = cfg[@"loc"];
        p.caption = cfg[@"cap"];
        p.hashtags = cfg[@"tags"];
        p.likes = [cfg[@"likes"] integerValue];
        p.commentsCount = [cfg[@"comments"] integerValue];
        p.timestamp = cfg[@"time"];
        p.imageKey = cfg[@"img"];
        p.aspectRatio = [cfg[@"ratio"] floatValue];
        p.isLiked = [cfg[@"isLiked"] boolValue];
        p.isBookmarked = [cfg[@"isBookmarked"] boolValue];
        
        IrisComment *c1 = [[IrisComment alloc] init];
        c1.commentId = [NSString stringWithFormat:@"%@_c1", p.postId];
        c1.username = cfg[@"c1_u"];
        c1.avatar = [NSString stringWithFormat:@"avatar_%@", cfg[@"c1_u"]];
        c1.text = cfg[@"c1_t"];
        c1.timestamp = @"1h ago";
        c1.likes = 14;
        c1.isLiked = NO;
        [p.comments addObject:c1];
        
        IrisComment *c2 = [[IrisComment alloc] init];
        c2.commentId = [NSString stringWithFormat:@"%@_c2", p.postId];
        c2.username = cfg[@"c2_u"];
        c2.avatar = [NSString stringWithFormat:@"avatar_%@", cfg[@"c2_u"]];
        c2.text = cfg[@"c2_t"];
        c2.timestamp = @"32m ago";
        c2.likes = 8;
        c2.isLiked = NO;
        [p.comments addObject:c2];
        
        [_posts addObject:p];
    }
    
    // 5. Notifications
    NSArray *mockNotifs = @[
        @{@"u": @"maya", @"a": @"avatar_maya", @"type": @"like", @"msg": @"liked your post.", @"time": @"12m ago", @"img": @"post_arch1", @"f": @NO},
        @{@"u": @"dev", @"a": @"avatar_dev", @"type": @"follow", @"msg": @"started following you.", @"time": @"45m ago", @"img": @"", @"f": @NO},
        @{@"u": @"sara", @"a": @"avatar_sara", @"type": @"comment", @"msg": @"commented: \"Need a cup of that right now!\"", @"time": @"2h ago", @"img": @"post_coffee1", @"f": @NO},
        @{@"u": @"jordan", @"a": @"avatar_jordan", @"type": @"mention", @"msg": @"mentioned you in a caption: \"collaboration with @alex on architectural study\"", @"time": @"4h ago", @"img": @"post_arch2", @"f": @NO},
        @{@"u": @"emily", @"a": @"avatar_emily", @"type": @"like", @"msg": @"liked your photo.", @"time": @"6h ago", @"img": @"post_nature1", @"f": @NO},
        @{@"u": @"noah", @"a": @"avatar_noah", @"type": @"follow", @"msg": @"started following you.", @"time": @"1d ago", @"img": @"", @"f": @YES},
        @{@"u": @"arjun", @"a": @"avatar_arjun", @"type": @"comment", @"msg": @"commented: \"Superb framing!\"", @"time": @"1d ago", @"img": @"post_neon1", @"f": @NO}
    ];
    
    int nId = 1;
    for (NSDictionary *nd in mockNotifs) {
        IrisNotification *n = [[IrisNotification alloc] init];
        n.notificationId = [NSString stringWithFormat:@"notif_%d", nId++];
        n.username = nd[@"u"];
        n.avatar = nd[@"a"];
        n.type = nd[@"type"];
        n.message = nd[@"msg"];
        n.timestamp = nd[@"time"];
        n.thumbnailImageKey = nd[@"img"];
        n.isFollowing = [nd[@"f"] boolValue];
        [_notifications addObject:n];
    }
}

- (void)toggleLikeForPost:(IrisPost *)post {
    if (!post) return;
    post.isLiked = !post.isLiked;
    if (post.isLiked) {
        post.likes += 1;
    } else {
        post.likes = MAX(0, post.likes - 1);
    }
}

- (void)toggleBookmarkForPost:(IrisPost *)post {
    if (!post) return;
    post.isBookmarked = !post.isBookmarked;
}

- (void)addComment:(NSString *)text toPost:(IrisPost *)post {
    if (!post || text.length == 0) return;
    IrisComment *c = [[IrisComment alloc] init];
    c.commentId = [NSString stringWithFormat:@"c_new_%lu", (unsigned long)post.comments.count + 1];
    c.username = self.currentUserProfile.username;
    c.avatar = self.currentUserProfile.avatar;
    c.text = text;
    c.timestamp = @"Just now";
    c.likes = 0;
    c.isLiked = NO;
    [post.comments addObject:c];
    post.commentsCount += 1;
}

- (void)addNewPostWithCaption:(NSString *)caption location:(NSString *)location audience:(NSString *)audience imageKey:(NSString *)imageKey {
    IrisPost *p = [[IrisPost alloc] init];
    p.postId = [NSString stringWithFormat:@"post_new_%lu", (unsigned long)self.posts.count + 1];
    p.username = self.currentUserProfile.username;
    p.displayName = self.currentUserProfile.displayName;
    p.avatar = self.currentUserProfile.avatar;
    p.location = location.length > 0 ? location : @"Tokyo, Japan";
    p.caption = caption.length > 0 ? caption : @"Captured with Iris on HakiOS ✨";
    p.hashtags = @"#iris #hakios #minimal #photography";
    p.likes = 1;
    p.commentsCount = 0;
    p.timestamp = @"Just now";
    p.imageKey = imageKey.length > 0 ? imageKey : @"post_new_created";
    p.aspectRatio = 1.0;
    p.isLiked = YES;
    p.isBookmarked = NO;
    
    // Add to beginning of feed
    [self.posts insertObject:p atIndex:0];
    self.currentUserProfile.postsCount += 1;
}

- (void)toggleFollowForUsername:(NSString *)username {
    IrisProfile *prof = self.profiles[username];
    if (prof) {
        prof.isFollowing = !prof.isFollowing;
        if (prof.isFollowing) {
            prof.followersCount += 1;
        } else {
            prof.followersCount = MAX(0, prof.followersCount - 1);
        }
    }
    for (IrisNotification *n in self.notifications) {
        if ([n.username isEqualToString:username]) {
            n.isFollowing = prof ? prof.isFollowing : !n.isFollowing;
        }
    }
}

- (NSArray<IrisPost *> *)searchPostsWithQuery:(NSString *)query {
    if (query.length == 0) return self.posts;
    NSString *q = [query lowercaseString];
    NSMutableArray *results = [NSMutableArray array];
    for (IrisPost *p in self.posts) {
        if ([[p.username lowercaseString] containsString:q] ||
            [[p.displayName lowercaseString] containsString:q] ||
            [[p.caption lowercaseString] containsString:q] ||
            [[p.hashtags lowercaseString] containsString:q] ||
            [[p.location lowercaseString] containsString:q]) {
            [results addObject:p];
        }
    }
    return results;
}

+ (UIImage *)imageForKey:(NSString *)key size:(CGSize)size title:(NSString *)title subtitle:(NSString *)subtitle {
    static NSCache *sImageCache = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        sImageCache = [[NSCache alloc] init];
        sImageCache.countLimit = 150;
    });
    
    NSString *cacheKey = [NSString stringWithFormat:@"%@_%.0fx%.0f", key, size.width, size.height];
    UIImage *cached = [sImageCache objectForKey:cacheKey];
    if (cached) return cached;
    
    // Generate beautiful procedural gradient photographic surface with subtle texture
    UIGraphicsBeginImageContextWithOptions(size, YES, 0.0);
    CGContextRef ctx = UIGraphicsGetCurrentContext();
    if (!ctx) return nil;
    
    // Color palettes hashed from key
    NSUInteger hash = [key hash];
    CGFloat hue1 = ((CGFloat)(hash % 360)) / 360.0;
    CGFloat hue2 = ((CGFloat)((hash + 45) % 360)) / 360.0;
    
    UIColor *c1 = [UIColor colorWithHue:hue1 saturation:0.65 brightness:0.25 alpha:1.0];
    UIColor *c2 = [UIColor colorWithHue:hue2 saturation:0.75 brightness:0.15 alpha:1.0];
    
    CGColorSpaceRef colorSpace = CGColorSpaceCreateDeviceRGB();
    NSArray *colors = @[(id)c1.CGColor, (id)c2.CGColor];
    CGFloat locs[] = {0.0, 1.0};
    CGGradientRef grad = CGGradientCreateWithColors(colorSpace, (__bridge CFArrayRef)colors, locs);
    CGContextDrawLinearGradient(ctx, grad, CGPointMake(0, 0), CGPointMake(size.width, size.height), 0);
    CGGradientRelease(grad);
    CGColorSpaceRelease(colorSpace);
    
    // Draw subtle photographic artistic grid lines or sunburst
    CGContextSetStrokeColorWithColor(ctx, [UIColor colorWithWhite:1.0 alpha:0.07].CGColor);
    CGContextSetLineWidth(ctx, 1.0);
    for (CGFloat y = 0; y < size.height; y += 40) {
        CGContextMoveToPoint(ctx, 0, y);
        CGContextAddLineToPoint(ctx, size.width, y);
    }
    for (CGFloat x = 0; x < size.width; x += 40) {
        CGContextMoveToPoint(ctx, x, 0);
        CGContextAddLineToPoint(ctx, x, size.height);
    }
    CGContextStrokePath(ctx);
    
    // Subtle central glow circle
    CGContextSaveGState(ctx);
    CGFloat circleRadius = MIN(size.width, size.height) * 0.35;
    CGPoint center = CGPointMake(size.width * 0.5, size.height * 0.45);
    UIBezierPath *circ = [UIBezierPath bezierPathWithArcCenter:center radius:circleRadius startAngle:0 endAngle:M_PI * 2 clockwise:YES];
    CGContextSetFillColorWithColor(ctx, [UIColor colorWithHue:hue1 saturation:0.8 brightness:0.8 alpha:0.18].CGColor);
    [circ fill];
    CGContextRestoreGState(ctx);
    
    // Elegant photography watermark/label in bottom corner
    if (title.length > 0 || subtitle.length > 0) {
        NSMutableParagraphStyle *style = [[NSMutableParagraphStyle alloc] init];
        style.alignment = NSTextAlignmentLeft;
        
        NSDictionary *titleAttr = @{
            NSFontAttributeName: [UIFont systemFontOfSize:MAX(12, size.width * 0.04) weight:UIFontWeightMedium],
            NSForegroundColorAttributeName: [UIColor colorWithWhite:1.0 alpha:0.92],
            NSParagraphStyleAttributeName: style
        };
        NSDictionary *subAttr = @{
            NSFontAttributeName: [UIFont systemFontOfSize:MAX(10, size.width * 0.03) weight:UIFontWeightRegular],
            NSForegroundColorAttributeName: [UIColor colorWithWhite:1.0 alpha:0.65],
            NSParagraphStyleAttributeName: style
        };
        
        CGFloat pad = 16.0;
        if (title.length > 0) {
            [title drawInRect:CGRectMake(pad, size.height - 48, size.width - pad * 2, 20) withAttributes:titleAttr];
        }
        if (subtitle.length > 0) {
            [subtitle drawInRect:CGRectMake(pad, size.height - 28, size.width - pad * 2, 18) withAttributes:subAttr];
        }
    }
    
    UIImage *img = UIGraphicsGetImageFromCurrentImageContext();
    UIGraphicsEndImageContext();
    
    if (img) {
        [sImageCache setObject:img forKey:cacheKey];
    }
    return img;
}

@end
